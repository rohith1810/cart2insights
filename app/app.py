"""Cart2Insights Streamlit dashboard.

    streamlit run app/app.py

Every number on screen comes from a SQL query in src/queries.py, run against
the database configured in .env. Filters in the sidebar are passed to every
query as bound parameters.
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.db import FEATURE_TABLES, get_engine, tables_exist  # noqa: E402
from src.queries import run_query  # noqa: E402

TEAL, AMBER, BRICK, SAGE, SLATE = "#0F4C5C", "#E09F3E", "#9E2A2B", "#8AA29E", "#3D5A6C"
STATUS_COLORS = {"On time": TEAL, "Delayed": BRICK, "Not delivered": SAGE}

st.set_page_config(page_title="Cart2Insights", layout="wide")
st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.6rem; color: #0F4C5C; }
[data-testid="stMetricLabel"] p { font-size: 0.9rem; }
.block-container { padding-top: 2rem; }
.insight { border-left: 4px solid #E09F3E; padding: 0.4rem 0.8rem; margin: 0.2rem 0 1rem;
           background: rgba(224, 159, 62, 0.08); }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ data
@st.cache_resource
def engine():
    return get_engine()


@st.cache_data(ttl=600, show_spinner="Running SQL query...")
def q(name: str, start: str, end: str, state: str) -> pd.DataFrame:
    return run_query(engine(), name, start, end, state)


@st.cache_data(ttl=600)
def filter_options() -> tuple[list[str], list[str]]:
    months = pd.read_sql("SELECT DISTINCT purchase_month FROM order_features "
                         "WHERE purchase_month IS NOT NULL ORDER BY purchase_month", engine())
    states = pd.read_sql("SELECT DISTINCT customer_state FROM order_features "
                         "WHERE customer_state IS NOT NULL ORDER BY customer_state", engine())
    return months["purchase_month"].tolist(), states["customer_state"].tolist()


def insight(text: str) -> None:
    st.markdown(f'<div class="insight">{text}</div>', unsafe_allow_html=True)


def style(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=50, b=10),
                      font=dict(size=13), title_font=dict(size=16),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", y=-0.2))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)")
    return fig


def show(fig: go.Figure, height: int = 380) -> None:
    st.plotly_chart(style(fig, height), width="stretch")


def fmt(value, spec: str = ",.1f", suffix: str = "") -> str:
    """Format a number, or show a dash when the query returned nothing."""
    return "–" if value is None or pd.isna(value) else f"{value:{spec}}{suffix}"


def nice(s: pd.Series) -> pd.Series:
    return s.astype(str).str.replace("_", " ")


# --------------------------------------------------------------- startup
try:
    ready = tables_exist(engine(), FEATURE_TABLES)
except Exception as exc:  # connection problems
    st.error(f"Could not connect to the database: {exc}\n\nCheck the settings in your .env file.")
    st.stop()
if not ready:
    st.error("The analysis tables are missing. Run `python run_pipeline.py` first, then reload.")
    st.stop()

months, states = filter_options()
if not months:
    st.warning("The order_features table is empty. Run the pipeline with the real dataset.")
    st.stop()

with st.sidebar:
    st.header("Filters")
    start, end = st.select_slider("Purchase month", options=months, value=(months[0], months[-1]))
    state = st.selectbox("Customer state", ["All"] + states)
    st.caption("Revenue = item price + freight for orders that were not canceled or unavailable.")

args = (start, end, state)
st.title("Cart2Insights: e-commerce performance")
st.caption(f"{start} to {end} · {'all states' if state == 'All' else state}")

tabs = st.tabs(["Business overview", "Sales", "Customers", "Sellers & products", "Delivery",
                "Customer experience"])

# ---------------------------------------------------------- 1. Overview
with tabs[0]:
    k = q("kpi_overview", *args).iloc[0]
    sellers = q("kpi_sellers", *args).iloc[0]
    if pd.isna(k["total_orders"]) or k["total_orders"] == 0:
        st.info("No orders match these filters. Widen the month range or choose another state.")
        st.stop()
    c = st.columns(6)
    c[0].metric("Total revenue (BRL)", f"{k['total_revenue']:,.0f}")
    c[1].metric("Orders", f"{int(k['total_orders']):,}")
    c[2].metric("Customers", f"{int(k['total_customers']):,}")
    c[3].metric("Sellers", f"{int(sellers['total_sellers']):,}")
    c[4].metric("Average order value", fmt(k["avg_order_value"], ",.2f"))
    c[5].metric("Average review", fmt(k["avg_review_score"], ".2f", " / 5"))

    m = q("monthly_revenue", *args)
    fig = go.Figure()
    fig.add_bar(x=m["purchase_month"], y=m["orders"], name="Orders", marker_color=AMBER,
                opacity=0.35, yaxis="y2")
    fig.add_scatter(x=m["purchase_month"], y=m["revenue"], name="Revenue (BRL)",
                    line=dict(color=TEAL, width=3), mode="lines+markers")
    fig.update_layout(title="Monthly revenue and orders",
                      yaxis=dict(title="Revenue (BRL)"),
                      yaxis2=dict(title="Orders", overlaying="y", side="right", showgrid=False))
    show(fig, 420)
    peak = m.loc[m["revenue"].idxmax()]
    insight(f"Revenue peaked in <b>{peak['purchase_month']}</b> at {peak['revenue']:,.0f} BRL. "
            "The first and last months in the data can be partial, so compare full months only.")

# ------------------------------------------------------------- 2. Sales
with tabs[1]:
    left, right = st.columns(2)
    with left:
        m = q("monthly_revenue", *args)
        fig = px.line(m, x="purchase_month", y="cumulative_revenue", markers=True,
                      title="Cumulative revenue (running total)",
                      labels={"purchase_month": "", "cumulative_revenue": "BRL"})
        fig.update_traces(line_color=TEAL)
        show(fig)
    with right:
        g = m.dropna(subset=["mom_growth_pct"])
        fig = px.bar(g, x="purchase_month", y="mom_growth_pct", title="Month-over-month growth",
                     labels={"purchase_month": "", "mom_growth_pct": "%"})
        fig.update_traces(marker_color=[TEAL if v >= 0 else BRICK for v in g["mom_growth_pct"]])
        show(fig)

    left, right = st.columns(2)
    with left:
        cat = q("revenue_by_category", *args)
        cat["category"] = nice(cat["category"])
        fig = px.bar(cat.iloc[::-1], x="revenue", y="category", orientation="h",
                     title="Revenue by category (top 15)", labels={"revenue": "BRL", "category": ""})
        fig.update_traces(marker_color=TEAL)
        show(fig, 480)
    with right:
        st_sales = q("sales_by_state", *args)
        fig = px.bar(st_sales, x="state", y="revenue", color="avg_order_value",
                     color_continuous_scale=["#D8E2DC", TEAL], title="Revenue by state",
                     labels={"revenue": "BRL", "state": "", "avg_order_value": "AOV"})
        show(fig, 480)

    st.subheader("Top-selling products")
    tp = q("top_products", *args)
    tp["category"] = nice(tp["category"])
    tp["product_id"] = tp["product_id"].str[:10] + "…"
    st.dataframe(tp, width="stretch", hide_index=True)
    if len(cat):
        share = 100 * cat["revenue"].head(3).sum() / cat["revenue"].sum()
        insight(f"The top 3 categories earn <b>{share:.1f}%</b> of revenue among the top 15. "
                f"<b>{cat['category'].iloc[0]}</b> leads.")

# --------------------------------------------------------- 3. Customers
with tabs[2]:
    rv = q("repeat_vs_new", *args)
    above = q("customers_above_average", *args).iloc[0]
    left, mid, right = st.columns([1, 1, 1.2])
    with left:
        fig = px.pie(rv, names="customer_type", values="customers", hole=0.55,
                     title="One-time vs repeat customers",
                     color="customer_type", color_discrete_map={"One-time": SAGE, "Repeat": TEAL})
        show(fig)
    with mid:
        sb = q("customer_spend_buckets", *args)
        sb["spend_band"] = sb["spend_band"].str[3:]
        fig = px.bar(sb, x="spend_band", y="customers", title="Customers by total spend (BRL)",
                     labels={"spend_band": "", "customers": "Customers"})
        fig.update_traces(marker_color=SLATE)
        show(fig)
    with right:
        cd = q("customer_distribution", *args)
        fig = px.bar(cd, x="state", y="customers", title="Customers by state",
                     labels={"state": "", "customers": "Customers"})
        fig.update_traces(marker_color=TEAL)
        show(fig)

    st.subheader("Top 10 customers by spend")
    tc = q("top_customers", *args)
    tc["customer_unique_id"] = tc["customer_unique_id"].str[:10] + "…"
    st.dataframe(tc, width="stretch", hide_index=True)
    rep = rv.set_index("customer_type")
    rep_pct = 100 * rep.loc["Repeat", "customers"] / rep["customers"].sum() if "Repeat" in rep.index else 0
    insight(f"Only <b>{rep_pct:.1f}%</b> of customers ordered more than once in this period. "
            f"{fmt(above['pct_of_customers'], '.1f', '%')} of customers spend more than the average customer.")

# ---------------------------------------------------- 4. Sellers & products
with tabs[3]:
    left, right = st.columns(2)
    with left:
        dec = q("seller_revenue_deciles", *args)
        fig = px.bar(dec, x="decile", y="revenue_share_pct",
                     title="Revenue share by seller decile (1 = top 10%)",
                     labels={"decile": "Seller decile", "revenue_share_pct": "% of revenue"})
        fig.update_traces(marker_color=[AMBER] + [TEAL] * (len(dec) - 1))
        fig.update_xaxes(dtick=1)
        show(fig)
    with right:
        cp = q("category_performance", *args)
        cp["category"] = nice(cp["category"])
        fig = px.scatter(cp, x="avg_order_value", y="avg_review", size="orders", color="delayed_pct",
                         hover_name="category", color_continuous_scale=[TEAL, AMBER, BRICK],
                         title="Categories: order value vs rating (size = orders)",
                         labels={"avg_order_value": "Average order value (BRL)",
                                 "avg_review": "Average review", "delayed_pct": "% delayed"})
        show(fig)

    left, right = st.columns(2)
    with left:
        st.subheader("Top sellers")
        ts = q("top_sellers", *args)
        ts["seller_id"] = ts["seller_id"].str[:10] + "…"
        st.dataframe(ts, width="stretch", hide_index=True)
    with right:
        st.subheader("Lowest-rated sellers (30+ reviews)")
        sr = q("seller_ratings", *args)
        sr["seller_id"] = sr["seller_id"].str[:10] + "…"
        st.dataframe(sr, width="stretch", hide_index=True)
    if len(dec):
        insight(f"The top 10% of sellers earn <b>{dec['revenue_share_pct'].iloc[0]:.1f}%</b> of item "
                "revenue. Low-rated sellers usually also have a high share of delayed orders.")

# ---------------------------------------------------------- 5. Delivery
with tabs[4]:
    dk = q("delivery_kpis", *args).iloc[0]
    c = st.columns(4)
    c[0].metric("Average delivery (days)", fmt(dk["avg_delivery_days"]))
    c[1].metric("Average estimate (days)", fmt(dk["avg_estimated_days"]))
    c[2].metric("Delayed orders", fmt(dk["delayed_orders"], ",.0f"))
    c[3].metric("Delayed share", fmt(dk["delayed_pct"], ".1f", "%"))

    left, right = st.columns(2)
    with left:
        oc = pd.DataFrame({"status": ["On time", "Delayed"],
                           "orders": [dk["on_time_orders"], dk["delayed_orders"]]})
        fig = px.pie(oc, names="status", values="orders", hole=0.55, title="On-time vs delayed",
                     color="status", color_discrete_map=STATUS_COLORS)
        show(fig)
    with right:
        dvr = q("delay_vs_review", *args)
        dvr["delay_band"] = dvr["delay_band"].str[3:]
        fig = px.bar(dvr, x="delay_band", y="avg_review", title="Review score by days early / late",
                     labels={"delay_band": "", "avg_review": "Average review"}, text="avg_review")
        fig.update_traces(marker_color=[TEAL if "early" in b or "day" in b else BRICK
                                        for b in dvr["delay_band"]])
        fig.update_yaxes(range=[0, 5])
        show(fig)

    ds = q("delivery_by_state", *args)
    fig = px.bar(ds, x="state", y="avg_delivery_days", color="delayed_pct",
                 color_continuous_scale=[TEAL, AMBER, BRICK], title="Delivery time by state",
                 labels={"state": "", "avg_delivery_days": "Average days", "delayed_pct": "% delayed"})
    show(fig)
    if len(ds):
        insight(f"<b>{ds['state'].iloc[0]}</b> waits longest ({ds['avg_delivery_days'].iloc[0]:.1f} days on "
                f"average). {fmt(dk['delayed_pct'], '.1f', '%')} of all deliveries arrive after the estimated date.")

# ------------------------------------------------- 6. Customer experience
with tabs[5]:
    left, right = st.columns(2)
    with left:
        rd = q("review_distribution", *args)
        fig = px.bar(rd, x="review_score", y="orders", text="pct", title="Review score distribution",
                     labels={"review_score": "Stars", "orders": "Orders"})
        fig.update_traces(marker_color=[BRICK, BRICK, SAGE, TEAL, TEAL], texttemplate="%{text}%")
        show(fig)
    with right:
        rvd = q("rating_vs_delivery", *args)
        fig = px.bar(rvd, x="delivery_status", y="avg_review", color="delivery_status",
                     color_discrete_map=STATUS_COLORS, text="avg_review",
                     title="Rating by delivery performance",
                     labels={"delivery_status": "", "avg_review": "Average review"})
        fig.update_layout(showlegend=False)
        fig.update_yaxes(range=[0, 5])
        show(fig)

    cp = q("category_performance", *args).sort_values("avg_review")
    cp["category"] = nice(cp["category"])
    fig = px.bar(cp, x="avg_review", y="category", orientation="h", color="delayed_pct",
                 color_continuous_scale=[TEAL, AMBER, BRICK], title="Average review by category",
                 labels={"avg_review": "Average review", "category": "", "delayed_pct": "% delayed"})
    fig.update_xaxes(range=[0, 5])
    show(fig, max(380, 26 * len(cp)))

    r = rvd.set_index("delivery_status")
    if {"On time", "Delayed"} <= set(r.index):
        insight(f"On-time orders average <b>{r.loc['On time', 'avg_review']:.2f}</b> stars; delayed "
                f"orders average <b>{r.loc['Delayed', 'avg_review']:.2f}</b>, and "
                f"{r.loc['Delayed', 'low_rating_pct']:.1f}% of them get 1-2 stars.")
