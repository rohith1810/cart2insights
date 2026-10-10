"""Step 9: statistical analysis.

Each test follows the same path:
hypothesis -> choose test -> check assumptions -> p-value -> decision -> business insight.
Results are returned as dictionaries and written to reports/stats_results.md.
"""
import numpy as np
import pandas as pd
from scipy import stats

from src.config import ALPHA, REPORTS_DIR


def _decision(p: float) -> str:
    return "Reject H0" if p < ALPHA else "Fail to reject H0"


def _fmt_p(p: float) -> str:
    return "< 0.0001" if p < 1e-4 else f"{p:.4f}"


def _p_text(p: float) -> str:
    """'p < 0.0001' or 'p = 0.0150' for use inside sentences."""
    return "p < 0.0001" if p < 1e-4 else f"p = {p:.4f}"


# ------------------------------------------------------------------ T-test
def ttest_delay_vs_review(of: pd.DataFrame) -> dict:
    """Do delayed orders receive lower review scores than on-time orders?"""
    d = of[of["delivery_status"].isin(["On time", "Delayed"]) & of["review_score"].notna()]
    on_time = d.loc[d["delivery_status"] == "On time", "review_score"].astype(float)
    delayed = d.loc[d["delivery_status"] == "Delayed", "review_score"].astype(float)

    levene = stats.levene(on_time, delayed)
    equal_var = levene.pvalue >= ALPHA
    # One-sided: H1 says delayed mean is LOWER.
    t = stats.ttest_ind(delayed, on_time, equal_var=equal_var, alternative="less")
    mw = stats.mannwhitneyu(delayed, on_time, alternative="less")
    pooled_sd = np.sqrt(((len(on_time) - 1) * on_time.var() + (len(delayed) - 1) * delayed.var())
                        / (len(on_time) + len(delayed) - 2))
    cohens_d = (on_time.mean() - delayed.mean()) / pooled_sd

    reject = t.pvalue < ALPHA
    return {
        "name": "T-test: delivery delay and review score",
        "question": "Do delayed orders receive significantly lower review scores than on-time orders?",
        "h0": "Mean review score of delayed orders = mean review score of on-time orders.",
        "h1": "Mean review score of delayed orders < mean review score of on-time orders.",
        "test": f"Independent two-sample t-test ({'Student' if equal_var else 'Welch'}, one-sided)",
        "assumptions": [
            f"Independent groups: each order is either on time ({len(on_time):,}) or delayed "
            f"({len(delayed):,}).",
            "Normality: review scores are discrete (1-5), but both groups are large, so by the "
            "central limit theorem the sample means are approximately normal.",
            f"Equal variances (Levene): {_p_text(levene.pvalue)} -> "
            f"{'equal variances assumed' if equal_var else 'unequal, so Welch t-test is used'}.",
            f"Robustness check (Mann-Whitney U, no normality needed): {_p_text(mw.pvalue)}.",
        ],
        "results": {
            "Mean review (on time)": round(on_time.mean(), 3),
            "Mean review (delayed)": round(delayed.mean(), 3),
            "t statistic": round(t.statistic, 3),
            "p-value": _fmt_p(t.pvalue),
            "Cohen's d": round(cohens_d, 3),
        },
        "decision": _decision(t.pvalue),
        "insight": (
            f"Delayed orders average {delayed.mean():.2f} stars vs {on_time.mean():.2f} for on-time "
            f"orders (effect size d = {cohens_d:.2f}). Delivery delay is linked to significantly "
            "lower satisfaction, so reducing delays should raise ratings."
            if reject else
            "No significant difference was found; delivery delay does not appear to drive ratings "
            "in this data."),
    }


# ------------------------------------------------------------------- ANOVA
def anova_category_vs_order_value(of: pd.DataFrame, top_n: int = 10) -> dict:
    """Does average order value differ across the top product categories?"""
    v = of[(of["is_valid_sale"] == 1) & of["main_category"].notna() & of["total_order_value"].notna()]
    top = v["main_category"].value_counts().head(top_n).index
    v = v[v["main_category"].isin(top)]
    groups = [g["total_order_value"].astype(float).values for _, g in v.groupby("main_category")]

    levene = stats.levene(*groups)
    f = stats.f_oneway(*groups)
    kw = stats.kruskal(*groups)
    grand = v["total_order_value"].mean()
    ss_between = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
    ss_total = ((v["total_order_value"] - grand) ** 2).sum()
    eta_sq = ss_between / ss_total

    means = v.groupby("main_category")["total_order_value"].mean().sort_values(ascending=False)
    reject = f.pvalue < ALPHA
    return {
        "name": "ANOVA: product category and order value",
        "question": "Does the average order value differ significantly across product categories?",
        "h0": f"Mean order value is the same in all {len(top)} categories.",
        "h1": "At least one category has a different mean order value.",
        "test": f"One-way ANOVA across the {len(top)} categories with the most orders",
        "assumptions": [
            "Independent observations: each order belongs to one main category.",
            "Normality: order values are right-skewed, but each group is large, so the F-test "
            "is reasonably robust; Kruskal-Wallis is reported as a check.",
            f"Equal variances (Levene): {_p_text(levene.pvalue)} -> "
            f"{'holds' if levene.pvalue >= ALPHA else 'violated, so rely on Kruskal-Wallis as well'}.",
            f"Kruskal-Wallis (non-parametric): {_p_text(kw.pvalue)}.",
        ],
        "results": {
            "F statistic": round(f.statistic, 3),
            "p-value": _fmt_p(f.pvalue),
            "Eta squared": round(eta_sq, 4),
            "Highest mean": f"{means.index[0]} ({means.iloc[0]:.2f})",
            "Lowest mean": f"{means.index[-1]} ({means.iloc[-1]:.2f})",
        },
        "decision": _decision(f.pvalue),
        "insight": (
            f"Spending differs by category: {means.index[0].replace('_', ' ')} orders average "
            f"{means.iloc[0]:.2f} BRL vs {means.iloc[-1]:.2f} for {means.index[-1].replace('_', ' ')}. "
            f"Category explains {100 * eta_sq:.1f}% of the variation in order value, so pricing and "
            "promotions should be planned per category."
            if reject else
            "Average order value is similar across the top categories."),
        "means_table": means.round(2).rename("mean_order_value").reset_index(),
    }


# -------------------------------------------------------------- Chi-square
def status_group(status: pd.Series) -> pd.Series:
    return np.select(
        [status == "delivered", status.isin(["canceled", "unavailable"])],
        ["Delivered", "Canceled/unavailable"], "In progress/other")


def chi_square_payment_vs_status(of: pd.DataFrame) -> dict:
    """Is the payment method associated with the order outcome?"""
    d = of[of["main_payment_type"].notna()].copy()
    d["status_group"] = status_group(d["order_status"])
    table = pd.crosstab(d["main_payment_type"], d["status_group"])
    # Drop rare payment types that would leave expected counts below 5.
    table = table[table.sum(axis=1) >= 30]

    chi2, p, dof, expected = stats.chi2_contingency(table)
    pct_ok = 100 * (expected >= 5).mean()
    n = table.values.sum()
    cramers_v = np.sqrt(chi2 / (n * (min(table.shape) - 1)))

    rates = (100 * table.div(table.sum(axis=1), axis=0)).round(2)
    cancel_col = "Canceled/unavailable"
    reject = p < ALPHA
    worst = rates[cancel_col].idxmax() if cancel_col in rates else None
    return {
        "name": "Chi-square: payment method and order status",
        "question": "Is there a significant association between payment method and order status?",
        "h0": "Payment method and order status are independent.",
        "h1": "Payment method and order status are associated.",
        "test": "Chi-square test of independence",
        "assumptions": [
            "Both variables are categorical and each order is counted once.",
            f"Expected counts >= 5 in {pct_ok:.0f}% of cells (rule of thumb: at least 80%).",
            "Order statuses grouped into Delivered, Canceled/unavailable and In progress/other "
            "so that no cell is too small.",
        ],
        "results": {
            "Chi-square": round(chi2, 3),
            "Degrees of freedom": dof,
            "p-value": _fmt_p(p),
            "Cramer's V": round(cramers_v, 4),
        },
        "decision": _decision(p),
        "insight": (
            f"Order outcome depends on payment method. {worst.replace('_', ' ')} has the highest "
            f"cancel/unavailable rate ({rates.loc[worst, cancel_col]:.2f}%). Cramer's V = "
            f"{cramers_v:.3f}, so the association is "
            f"{'weak' if cramers_v < 0.1 else 'moderate' if cramers_v < 0.3 else 'strong'}; "
            "follow up on slow or failed payments for that method."
            if reject and worst else
            "No significant association: order outcomes are similar across payment methods."),
        "contingency_pct": rates.reset_index(),
    }


# -------------------------------------------------------------------- runner
def run_all_tests(of: pd.DataFrame) -> list[dict]:
    results = [ttest_delay_vs_review(of), anova_category_vs_order_value(of),
               chi_square_payment_vs_status(of)]
    write_report(results)
    return results


def write_report(results: list[dict]) -> None:
    lines = ["# Statistical analysis", "",
             f"Significance level: alpha = {ALPHA}. Generated by `src/stats_tests.py`.", ""]
    for r in results:
        lines += [f"## {r['name']}", "", f"**Question:** {r['question']}", "",
                  f"- H0: {r['h0']}", f"- H1: {r['h1']}", "", f"**Test:** {r['test']}", "",
                  "**Assumption checks:**", ""]
        lines += [f"- {a}" for a in r["assumptions"]]
        lines += ["", "| Result | Value |", "| --- | --- |"]
        lines += [f"| {k} | {v} |" for k, v in r["results"].items()]
        lines += ["", f"**Decision:** {r['decision']}", "", f"**Business insight:** {r['insight']}", ""]
        for key in ("means_table", "contingency_pct"):
            if key in r:
                lines += [r[key].to_markdown(index=False), ""]
    (REPORTS_DIR / "stats_results.md").write_text("\n".join(lines))
