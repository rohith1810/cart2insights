"""Step 11: business insights.

Pulls the key numbers from SQL and the statistical tests and writes each
finding as Observation -> Interpretation -> Business impact, followed by
recommendations, to reports/business_insights.md.

The wording is a starting draft generated from the numbers. Read it, check it
against the charts, and rewrite it in your own words before presenting.
"""
import pandas as pd
from sqlalchemy.engine import Engine

from src.config import REPORTS_DIR
from src.queries import run_query


def _month_range(engine: Engine) -> tuple[str, str]:
    m = pd.read_sql("SELECT MIN(purchase_month) AS lo, MAX(purchase_month) AS hi "
                    "FROM order_features", engine)
    return m.loc[0, "lo"], m.loc[0, "hi"]


def build_insights(engine: Engine, stats_results: list[dict]) -> tuple[list[dict], pd.Series, tuple[str, str]]:
    lo, hi = _month_range(engine)

    def q(name):
        return run_query(engine, name, lo, hi, "All")

    kpi = q("kpi_overview").iloc[0]
    states = q("sales_by_state")
    repeat = q("repeat_vs_new").set_index("customer_type")
    deciles = q("seller_revenue_deciles")
    cats = q("revenue_by_category")
    deliv = q("delivery_kpis").iloc[0]
    rating = q("rating_vs_delivery").set_index("delivery_status")
    by_state = q("delivery_by_state")
    ttest, anova, chi = stats_results

    top3_share = 100 * states["revenue"].head(3).sum() / states["revenue"].sum()
    repeat_pct = 100 * repeat.loc["Repeat", "customers"] / repeat["customers"].sum() \
        if "Repeat" in repeat.index else 0.0
    top_decile = deciles.loc[deciles["decile"] == 1, "revenue_share_pct"].iloc[0]
    top_cat_share = 100 * cats["revenue"].head(3).sum() / cats["revenue"].sum()
    slowest = by_state.iloc[0]
    cramers_v = chi["results"]["Cramer's V"]

    insights = [
        {
            "title": "Sales are concentrated in a few states",
            "observation": f"The top 3 states ({', '.join(states['state'].head(3))}) generate "
                           f"{top3_share:.1f}% of revenue.",
            "interpretation": "Demand follows population and income centres in the south-east.",
            "impact": "Marketing spend and warehouse capacity give the best return in these states; "
                      "other states are a growth opportunity.",
        },
        {
            "title": "Very few customers come back",
            "observation": f"Only {repeat_pct:.1f}% of customers placed more than one order.",
            "interpretation": "The platform depends on winning new customers for almost every sale.",
            "impact": "A retention programme (follow-up emails, loyalty discounts) could lift revenue "
                      "without raising acquisition cost.",
        },
        {
            "title": "A small group of sellers earns most revenue",
            "observation": f"The top 10% of sellers earn {top_decile:.1f}% of item revenue.",
            "interpretation": "Seller revenue is highly concentrated.",
            "impact": "Losing a top seller is a real risk; key-account support for these sellers "
                      "and onboarding help for small sellers would spread the risk.",
        },
        {
            "title": "Three categories lead item revenue",
            "observation": f"{', '.join(cats['category'].head(3).str.replace('_', ' '))} make up "
                           f"{top_cat_share:.1f}% of revenue among the top 15 categories.",
            "interpretation": anova["insight"],
            "impact": "Stock, promotions and seller recruitment should prioritise these categories.",
        },
        {
            "title": f"{deliv['delayed_pct']:.1f}% of deliveries arrive late",
            "observation": f"{deliv['delayed_pct']:.1f}% of delivered orders arrived after the "
                           f"estimated date; average delivery takes {deliv['avg_delivery_days']:.1f} "
                           f"days against an average estimate of {deliv['avg_estimated_days']:.1f}.",
            "interpretation": "Estimates are usually generous, so the late orders are real failures "
                              "rather than tight promises.",
            "impact": "Every late order is a likely low review (see next insight).",
        },
        {
            "title": "Late delivery is the clearest driver of bad reviews",
            "observation": f"On-time orders average {rating.loc['On time', 'avg_review']:.2f} stars; "
                           f"delayed orders average {rating.loc['Delayed', 'avg_review']:.2f}, and "
                           f"{rating.loc['Delayed', 'low_rating_pct']:.1f}% of delayed orders get 1-2 "
                           "stars.",
            "interpretation": ttest["insight"] + f" (t-test decision: {ttest['decision']}).",
            "impact": "Improving delivery reliability is the most direct lever on customer satisfaction.",
        },
        {
            "title": "Remote states wait longest",
            "observation": f"{slowest['state']} has the longest average delivery "
                           f"({slowest['avg_delivery_days']:.1f} days) with "
                           f"{slowest['delayed_pct']:.1f}% of orders late.",
            "interpretation": "Distance from the seller hubs drives delivery time and delay.",
            "impact": "Regional carriers or local fulfilment in these states would cut delays.",
        },
        {
            "title": "Payment method and order outcome",
            "observation": f"Chi-square decision: {chi['decision']} "
                           f"(p-value {chi['results']['p-value']}, Cramer's V {cramers_v}).",
            "interpretation": chi["insight"],
            "impact": "Where the association is real but weak, payment method is a secondary factor "
                      "compared with delivery.",
        },
    ]
    return insights, kpi, (lo, hi)


RECOMMENDATIONS = [
    "Cut late deliveries: track seller dispatch time and warn or penalise sellers who ship late.",
    "Tighten delivery estimates per state so customers get realistic promises.",
    "Launch a second-purchase campaign (discount or free shipping) within 30 days of the first order.",
    "Give the top 10% of sellers dedicated support, and help small sellers grow to reduce concentration.",
    "Focus marketing budget on the leading categories and states, and test growth campaigns elsewhere.",
    "Contact customers after a delayed delivery to recover the experience before they leave a review.",
]


def write_insights(engine: Engine, stats_results: list[dict]) -> None:
    insights, kpi, (lo, hi) = build_insights(engine, stats_results)
    lines = [
        "# Business insights and recommendations", "",
        f"Period covered: {lo} to {hi}. Draft generated by `src/insights.py`; "
        "review and rewrite in your own words before presenting.", "",
        "## Headline numbers", "",
        "| Metric | Value |", "| --- | --- |",
        f"| Total revenue (BRL) | {kpi['total_revenue']:,.2f} |",
        f"| Orders | {int(kpi['total_orders']):,} |",
        f"| Customers | {int(kpi['total_customers']):,} |",
        f"| Average order value (BRL) | {kpi['avg_order_value']:,.2f} |",
        f"| Average review score | {kpi['avg_review_score']:.2f} |", "",
        "## Insights", "",
    ]
    for i, ins in enumerate(insights, 1):
        lines += [f"### {i}. {ins['title']}", "",
                  f"- **Observation:** {ins['observation']}",
                  f"- **Interpretation:** {ins['interpretation']}",
                  f"- **Business impact:** {ins['impact']}", ""]
    lines += ["## Recommendations", ""] + [f"{i}. {r}" for i, r in enumerate(RECOMMENDATIONS, 1)]
    (REPORTS_DIR / "business_insights.md").write_text("\n".join(lines) + "\n")
