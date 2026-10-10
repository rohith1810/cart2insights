"""Step 8: exploratory data analysis.

Data is pulled from SQL, then each function draws one chart, saves it to
reports/figures/ and returns a one-line finding computed from the data.
`run_eda` writes all findings to reports/eda_summary.md.
"""
import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from src.config import FIGURES_DIR, REPORTS_DIR  # noqa: E402

log = logging.getLogger(__name__)
logging.getLogger("matplotlib.category").setLevel(logging.WARNING)

PALETTE = {"teal": "#0F4C5C", "amber": "#E09F3E", "brick": "#9E2A2B", "sage": "#8AA29E",
           "slate": "#3D5A6C"}
STATUS_COLORS = {"On time": PALETTE["teal"], "Delayed": PALETTE["brick"]}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams.update({"figure.dpi": 110, "axes.titleweight": "bold", "axes.titlesize": 12})


# ------------------------------------------------------------- data access
def load_order_features(engine: Engine) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM order_features", engine,
                       parse_dates=["order_purchase_timestamp"])


def load_item_categories(engine: Engine) -> pd.DataFrame:
    sql = """
    SELECT oi.order_id, oi.price, oi.freight_value,
           COALESCE(t.product_category_name_english, p.product_category_name) AS category
    FROM order_items oi
    JOIN order_features o ON o.order_id = oi.order_id AND o.is_valid_sale = 1
    JOIN products p ON p.product_id = oi.product_id
    LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
    """
    return pd.read_sql(sql, engine)


def _save(fig, name: str) -> str:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / f"{name}.png", bbox_inches="tight")
    plt.close(fig)
    return f"figures/{name}.png"


# -------------------------------------------------------------- univariate
def review_score_distribution(of):
    s = of["review_score"].dropna().astype(int)
    counts = s.value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(counts.index, counts.values, color=PALETTE["teal"])
    ax.set(title="Review score distribution", xlabel="Review score", ylabel="Orders")
    pct5, pct1 = 100 * (s == 5).mean(), 100 * (s == 1).mean()
    return _save(fig, "01_review_scores"), (
        f"{pct5:.1f}% of reviews are 5 stars and {pct1:.1f}% are 1 star; "
        f"the average is {s.mean():.2f}.")


def order_value_distribution(of):
    v = of.loc[of["is_valid_sale"] == 1, "total_order_value"].dropna()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(v, bins=np.logspace(np.log10(max(v.min(), 1)), np.log10(v.max()), 50),
            color=PALETTE["teal"])
    ax.set_xscale("log")
    ax.axvline(v.median(), color=PALETTE["amber"], lw=2, label=f"Median {v.median():.0f}")
    ax.set(title="Order value distribution (log scale)", xlabel="Order value (BRL)", ylabel="Orders")
    ax.legend()
    return _save(fig, "02_order_value"), (
        f"Order values are right-skewed: median {v.median():.2f}, mean {v.mean():.2f}, "
        f"95th percentile {v.quantile(0.95):.2f} BRL.")


def delivery_days_distribution(of):
    d = of["delivery_days"].dropna()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(d.clip(upper=60), bins=60, color=PALETTE["slate"])
    ax.axvline(d.median(), color=PALETTE["amber"], lw=2, label=f"Median {d.median():.1f} days")
    ax.set(title="Delivery time (capped at 60 days)", xlabel="Days from purchase to delivery",
           ylabel="Orders")
    ax.legend()
    return _save(fig, "03_delivery_days"), (
        f"Median delivery takes {d.median():.1f} days; {100 * (d > 30).mean():.1f}% of "
        "deliveries take more than 30 days.")


def payment_type_share(of):
    s = of.loc[of["is_valid_sale"] == 1, "main_payment_type"].value_counts(normalize=True) * 100
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh(s.index[::-1], s.values[::-1], color=PALETTE["teal"])
    ax.set(title="Main payment method", xlabel="Share of orders (%)")
    return _save(fig, "04_payment_types"), (
        f"{s.index[0].replace('_', ' ')} is the main method for {s.iloc[0]:.1f}% of orders.")


# --------------------------------------------------------------- bivariate
def review_by_delivery_status(of):
    d = of[of["delivery_status"].isin(["On time", "Delayed"]) & of["review_score"].notna()]
    m = d.groupby("delivery_status")["review_score"].mean().reindex(["On time", "Delayed"])
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(m.index, m.values, color=[STATUS_COLORS[i] for i in m.index])
    for i, v in enumerate(m.values):
        ax.text(i, v + 0.05, f"{v:.2f}", ha="center")
    ax.set(title="Average review by delivery status", ylabel="Average review score", ylim=(0, 5))
    return _save(fig, "05_review_by_delivery"), (
        f"On-time orders average {m['On time']:.2f} stars vs {m['Delayed']:.2f} for delayed "
        f"orders, a gap of {m['On time'] - m['Delayed']:.2f}.")


def review_by_delay_band(of):
    d = of[of["delivery_status"].isin(["On time", "Delayed"]) & of["review_score"].notna()].copy()
    bins = [-np.inf, -8, -1, 0, 3, 7, np.inf]
    labels = ["8+ early", "1-7 early", "On the day", "1-3 late", "4-7 late", "8+ late"]
    d["band"] = pd.cut(d["delivery_delay_days"].astype(float), bins=bins, labels=labels)
    m = d.groupby("band", observed=False)["review_score"].mean()
    fig, ax = plt.subplots(figsize=(8, 4))
    colors = [PALETTE["teal"]] * 3 + [PALETTE["brick"]] * 3
    ax.bar(m.index.astype(str), m.values, color=colors)
    ax.set(title="Average review by days early / late", xlabel="Delivery vs estimated date",
           ylabel="Average review score", ylim=(0, 5))
    return _save(fig, "06_review_by_delay_band"), (
        f"Reviews fall steadily with lateness: {m.iloc[0]:.2f} for orders 8+ days early "
        f"vs {m.iloc[-1]:.2f} for orders 8+ days late.")


def revenue_by_category(items):
    r = items.groupby("category")["price"].sum().sort_values(ascending=False).head(15)
    share = 100 * r.sum() / items["price"].sum()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(r.index[::-1].str.replace("_", " "), r.values[::-1] / 1000, color=PALETTE["teal"])
    ax.set(title="Top 15 categories by item revenue", xlabel="Revenue (thousand BRL)")
    return _save(fig, "07_revenue_by_category"), (
        f"The top 15 of {items['category'].nunique()} categories earn {share:.1f}% of item "
        f"revenue; the largest is {r.index[0].replace('_', ' ')}.")


def orders_by_state(of):
    s = of[of["is_valid_sale"] == 1]["customer_state"].value_counts()
    top3 = 100 * s.head(3).sum() / s.sum()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(s.index, s.values, color=PALETTE["slate"])
    ax.set(title="Orders by customer state", xlabel="State", ylabel="Orders")
    return _save(fig, "08_orders_by_state"), (
        f"{', '.join(s.index[:3])} together place {top3:.1f}% of all orders.")


# ------------------------------------------------------------------- trend
def monthly_trend(of):
    m = (of[of["is_valid_sale"] == 1].groupby("purchase_month")
         .agg(revenue=("total_order_value", "sum"), orders=("order_id", "count")))
    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax1.plot(m.index, m["revenue"] / 1000, color=PALETTE["teal"], marker="o", lw=2)
    ax1.set(title="Monthly revenue and orders", ylabel="Revenue (thousand BRL)")
    ax2 = ax1.twinx()
    ax2.bar(m.index, m["orders"], color=PALETTE["amber"], alpha=0.3)
    ax2.set_ylabel("Orders")
    ax2.grid(False)
    ax1.tick_params(axis="x", rotation=60)
    ax1.grid(axis="x", visible=False)
    ax1.set_zorder(ax2.get_zorder() + 1)
    ax1.patch.set_visible(False)
    peak = m["revenue"].idxmax()
    return _save(fig, "09_monthly_trend"), (
        f"Revenue peaks in {peak} at {m.loc[peak, 'revenue']:,.0f} BRL "
        f"({m.loc[peak, 'orders']:,} orders). Check the first and last months: they may be partial.")


def weekday_hour_heatmap(of):
    h = (of[of["is_valid_sale"] == 1].pivot_table(index="purchase_weekday", columns="purchase_hour",
                                                   values="order_id", aggfunc="count")
         .reindex(WEEKDAYS).fillna(0))
    fig, ax = plt.subplots(figsize=(11, 4))
    sns.heatmap(h, cmap="YlGnBu", ax=ax, cbar_kws={"label": "Orders"})
    ax.set(title="Orders by weekday and hour", xlabel="Hour of day", ylabel="")
    busiest_day = h.sum(axis=1).idxmax()
    busiest_hour = h.sum(axis=0).idxmax()
    return _save(fig, "10_weekday_hour"), (
        f"{busiest_day} is the busiest day and {busiest_hour}:00 the busiest hour for purchases.")


# ------------------------------------------------------------ multivariate
def state_delay_vs_review(of):
    d = of[of["delivery_status"].isin(["On time", "Delayed"])]
    s = (d.groupby("customer_state")
         .agg(orders=("order_id", "count"), delayed_rate=("is_delayed", "mean"),
              avg_review=("review_score", "mean"), avg_days=("delivery_days", "mean")))
    s = s[s["orders"] >= 30].astype(float)
    fig, ax = plt.subplots(figsize=(8, 5))
    sc = ax.scatter(100 * s["delayed_rate"], s["avg_review"], s=80 + 900 * np.sqrt(s["orders"] / s["orders"].max()),
                    c=s["avg_days"], cmap="viridis_r", alpha=0.8, edgecolor="white")
    for state, row in s.iterrows():
        ax.annotate(state, (100 * row["delayed_rate"], row["avg_review"]), fontsize=8,
                    ha="center", va="center")
    fig.colorbar(sc, label="Average delivery days")
    ax.set(title="States: delay rate vs rating (size = orders)", xlabel="Delayed orders (%)",
           ylabel="Average review score")
    corr = s["delayed_rate"].corr(s["avg_review"])
    worst = s["delayed_rate"].idxmax()
    return _save(fig, "11_state_delay_vs_review"), (
        f"Across states, delay rate and average rating have a correlation of {corr:.2f}; "
        f"{worst} has the highest delay rate ({100 * s.loc[worst, 'delayed_rate']:.1f}%).")


def correlation_matrix(of):
    cols = ["total_order_value", "freight_value", "items_count", "payment_installments",
            "delivery_days", "delivery_delay_days", "review_score"]
    c = of[cols].astype(float).corr()
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(c, annot=True, fmt=".2f", cmap="RdBu_r", vmin=-1, vmax=1, ax=ax, square=True)
    ax.set_title("Correlation between numeric features")
    r = c["review_score"].drop("review_score")
    top = r.abs().idxmax()
    return _save(fig, "12_correlation"), (
        f"The feature most correlated with review score is {top.replace('_', ' ')} "
        f"(r = {r[top]:.2f}).")


# -------------------------------------------------------------------- runner
def run_eda(engine: Engine) -> list[tuple[str, str, str]]:
    """Draw every chart and write reports/eda_summary.md. Returns (section, figure, finding)."""
    of = load_order_features(engine)
    items = load_item_categories(engine)
    steps = [
        ("Univariate", review_score_distribution, of),
        ("Univariate", order_value_distribution, of),
        ("Univariate", delivery_days_distribution, of),
        ("Univariate", payment_type_share, of),
        ("Bivariate", review_by_delivery_status, of),
        ("Bivariate", review_by_delay_band, of),
        ("Bivariate", revenue_by_category, items),
        ("Bivariate", orders_by_state, of),
        ("Trend", monthly_trend, of),
        ("Trend", weekday_hour_heatmap, of),
        ("Multivariate", state_delay_vs_review, of),
        ("Correlation", correlation_matrix, of),
    ]
    results = []
    for section, func, data in steps:
        fig_path, finding = func(data)
        results.append((section, fig_path, finding))
        log.info("EDA %-12s %s", section, finding)

    lines = ["# EDA summary", "", "Generated by `src/eda.py` from the SQL database.", ""]
    current = None
    for section, fig_path, finding in results:
        if section != current:
            lines += [f"## {section}", ""]
            current = section
        lines += [f"![{fig_path}]({fig_path})", "", f"**Finding:** {finding}", ""]
    (REPORTS_DIR / "eda_summary.md").write_text("\n".join(lines))
    return results
