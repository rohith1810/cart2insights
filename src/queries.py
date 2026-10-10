"""Step 10: SQL business queries.

Every query answers one business question and is used by the Streamlit dashboard.
Together they use SELECT/WHERE/ORDER BY, GROUP BY/HAVING, joins, subqueries,
CTEs, window functions (RANK, NTILE, LAG, running SUM) and aggregations.

All queries share the same dashboard filters, passed as bound parameters:
  :start_month, :end_month  ('YYYY-MM')   and   :state  (a state code or 'All')
The SQL is written for PostgreSQL (and also runs on SQLite 3.25+ for local tests).
PostgreSQL's ROUND(value, digits) only accepts NUMERIC, so every rounded value is
cast with CAST(... AS NUMERIC) first (float columns are DOUBLE PRECISION).
"""
from decimal import Decimal

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.config import SQL_DIR

FILTERS = ("o.purchase_month BETWEEN :start_month AND :end_month "
           "AND (:state = 'All' OR o.customer_state = :state)")
VALID = "o.is_valid_sale = 1"
CATEGORY = "COALESCE(t.product_category_name_english, p.product_category_name)"

QUERIES: dict[str, tuple[str, str]] = {
    # ------------------------------------------------------ 1. Business overview
    "kpi_overview": ("Headline KPIs for valid (not canceled) orders.", f"""
SELECT
    ROUND(CAST(SUM(o.total_order_value) AS NUMERIC), 2)   AS total_revenue,
    COUNT(DISTINCT o.order_id)           AS total_orders,
    COUNT(DISTINCT o.customer_unique_id) AS total_customers,
    ROUND(CAST(AVG(o.total_order_value) AS NUMERIC), 2)   AS avg_order_value,
    ROUND(CAST(AVG(o.review_score) AS NUMERIC), 2)        AS avg_review_score
FROM order_features o
WHERE {VALID} AND {FILTERS}"""),

    "kpi_sellers": ("Number of sellers with at least one valid sale.", f"""
SELECT COUNT(DISTINCT oi.seller_id) AS total_sellers
FROM order_items oi
JOIN order_features o ON o.order_id = oi.order_id
WHERE {VALID} AND {FILTERS}"""),

    # ---------------------------------------------------------- 2. Sales analysis
    "monthly_revenue": ("Monthly revenue with running total and month-over-month growth.", f"""
WITH monthly AS (
    SELECT o.purchase_month,
           COUNT(*)                AS orders,
           SUM(o.total_order_value) AS revenue
    FROM order_features o
    WHERE {VALID} AND {FILTERS}
    GROUP BY o.purchase_month
)
SELECT purchase_month,
       orders,
       ROUND(CAST(revenue AS NUMERIC), 2) AS revenue,
       ROUND(CAST(SUM(revenue) OVER (ORDER BY purchase_month) AS NUMERIC), 2) AS cumulative_revenue,
       ROUND(CAST(100.0 * (revenue - LAG(revenue) OVER (ORDER BY purchase_month))
             / LAG(revenue) OVER (ORDER BY purchase_month) AS NUMERIC), 2) AS mom_growth_pct
FROM monthly
ORDER BY purchase_month"""),

    "revenue_by_category": ("Item revenue by product category (categories with 20+ items).", f"""
SELECT {CATEGORY}                  AS category,
       COUNT(DISTINCT oi.order_id) AS orders,
       COUNT(*)                    AS items_sold,
       ROUND(CAST(SUM(oi.price) AS NUMERIC), 2)     AS revenue,
       ROUND(CAST(AVG(oi.price) AS NUMERIC), 2)     AS avg_item_price
FROM order_items oi
JOIN order_features o            ON o.order_id = oi.order_id
JOIN products p                  ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
WHERE {VALID} AND {FILTERS}
GROUP BY {CATEGORY}
HAVING COUNT(*) >= 20
ORDER BY revenue DESC
LIMIT 15"""),

    "top_products": ("Top 10 products by units sold.", f"""
SELECT oi.product_id,
       {CATEGORY}              AS category,
       COUNT(*)                AS units_sold,
       ROUND(CAST(SUM(oi.price) AS NUMERIC), 2) AS revenue
FROM order_items oi
JOIN order_features o            ON o.order_id = oi.order_id
JOIN products p                  ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
WHERE {VALID} AND {FILTERS}
GROUP BY oi.product_id, {CATEGORY}
ORDER BY units_sold DESC, revenue DESC
LIMIT 10"""),

    "sales_by_state": ("Orders, revenue and average order value by customer state.", f"""
SELECT o.customer_state                   AS state,
       COUNT(*)                           AS orders,
       ROUND(CAST(SUM(o.total_order_value) AS NUMERIC), 2) AS revenue,
       ROUND(CAST(AVG(o.total_order_value) AS NUMERIC), 2) AS avg_order_value
FROM order_features o
WHERE {VALID} AND {FILTERS}
GROUP BY o.customer_state
ORDER BY revenue DESC"""),

    # ------------------------------------------------------- 3. Customer analysis
    "customer_distribution": ("Customers by state.", f"""
SELECT o.customer_state AS state,
       COUNT(DISTINCT o.customer_unique_id) AS customers
FROM order_features o
WHERE {VALID} AND {FILTERS}
GROUP BY o.customer_state
ORDER BY customers DESC"""),

    "customer_spend_buckets": ("How many customers fall in each total-spend band.", f"""
WITH spend AS (
    SELECT o.customer_unique_id, SUM(o.total_order_value) AS total_spend
    FROM order_features o
    WHERE {VALID} AND {FILTERS}
    GROUP BY o.customer_unique_id
)
SELECT CASE
           WHEN total_spend < 50  THEN '1. Under 50'
           WHEN total_spend < 100 THEN '2. 50-100'
           WHEN total_spend < 200 THEN '3. 100-200'
           WHEN total_spend < 500 THEN '4. 200-500'
           ELSE '5. 500+'
       END                        AS spend_band,
       COUNT(*)                   AS customers,
       ROUND(CAST(SUM(total_spend) AS NUMERIC), 2) AS revenue
FROM spend
GROUP BY spend_band
ORDER BY spend_band"""),

    "repeat_vs_new": ("One-time vs repeat customers in the selected period.", f"""
WITH cust AS (
    SELECT o.customer_unique_id,
           COUNT(DISTINCT o.order_id) AS orders,
           SUM(o.total_order_value)   AS spend
    FROM order_features o
    WHERE {VALID} AND {FILTERS}
    GROUP BY o.customer_unique_id
)
SELECT CASE WHEN orders > 1 THEN 'Repeat' ELSE 'One-time' END AS customer_type,
       COUNT(*)             AS customers,
       ROUND(CAST(SUM(spend) AS NUMERIC), 2) AS revenue,
       ROUND(CAST(AVG(spend) AS NUMERIC), 2) AS avg_spend
FROM cust
GROUP BY customer_type"""),

    "top_customers": ("Top 10 customers by spend, ranked with a window function.", f"""
WITH cust AS (
    SELECT o.customer_unique_id,
           MAX(o.customer_state)      AS state,
           COUNT(DISTINCT o.order_id) AS orders,
           SUM(o.total_order_value)   AS spend
    FROM order_features o
    WHERE {VALID} AND {FILTERS}
    GROUP BY o.customer_unique_id
)
SELECT customer_unique_id, state, orders, total_spend, spend_rank
FROM (
    SELECT customer_unique_id, state, orders,
           ROUND(CAST(spend AS NUMERIC), 2) AS total_spend,
           RANK() OVER (ORDER BY spend DESC) AS spend_rank
    FROM cust
) ranked
WHERE spend_rank <= 10
ORDER BY spend_rank"""),

    "customers_above_average": ("Customers whose spend is above the average (subqueries).", f"""
SELECT COUNT(*) AS customers_above_avg,
       ROUND(CAST(100.0 * COUNT(*) / (
           SELECT COUNT(DISTINCT o.customer_unique_id)
           FROM order_features o WHERE {VALID} AND {FILTERS}) AS NUMERIC), 2) AS pct_of_customers
FROM (
    SELECT o.customer_unique_id, SUM(o.total_order_value) AS spend
    FROM order_features o
    WHERE {VALID} AND {FILTERS}
    GROUP BY o.customer_unique_id
) c
WHERE c.spend > (
    SELECT AVG(s.spend) FROM (
        SELECT SUM(o.total_order_value) AS spend
        FROM order_features o
        WHERE {VALID} AND {FILTERS}
        GROUP BY o.customer_unique_id) s)"""),

    # ------------------------------------------------- 4. Seller & product analysis
    "top_sellers": ("Top 15 sellers: overall rank, rank within state and revenue share.", f"""
WITH seller_sales AS (
    SELECT oi.seller_id, s.seller_state,
           COUNT(DISTINCT oi.order_id) AS orders,
           SUM(oi.price)               AS revenue
    FROM order_items oi
    JOIN order_features o ON o.order_id = oi.order_id
    JOIN sellers s        ON s.seller_id = oi.seller_id
    WHERE {VALID} AND {FILTERS}
    GROUP BY oi.seller_id, s.seller_state
)
SELECT seller_id, seller_state, orders,
       ROUND(CAST(revenue AS NUMERIC), 2) AS revenue,
       RANK() OVER (ORDER BY revenue DESC) AS overall_rank,
       RANK() OVER (PARTITION BY seller_state ORDER BY revenue DESC) AS rank_in_state,
       ROUND(CAST(100.0 * revenue / SUM(revenue) OVER () AS NUMERIC), 2) AS revenue_share_pct
FROM seller_sales
ORDER BY revenue DESC
LIMIT 15"""),

    "seller_revenue_deciles": ("Share of revenue earned by each 10% of sellers (NTILE).", f"""
WITH s AS (
    SELECT oi.seller_id, SUM(oi.price) AS revenue
    FROM order_items oi
    JOIN order_features o ON o.order_id = oi.order_id
    WHERE {VALID} AND {FILTERS}
    GROUP BY oi.seller_id
),
d AS (
    SELECT seller_id, revenue, NTILE(10) OVER (ORDER BY revenue DESC) AS decile
    FROM s
)
SELECT decile,
       COUNT(*)             AS sellers,
       ROUND(CAST(SUM(revenue) AS NUMERIC), 2) AS revenue,
       ROUND(CAST(100.0 * SUM(revenue) / (SELECT SUM(revenue) FROM s) AS NUMERIC), 2) AS revenue_share_pct
FROM d
GROUP BY decile
ORDER BY decile"""),

    "seller_ratings": ("Lowest-rated sellers with 30+ reviewed orders.", f"""
SELECT so.seller_id,
       COUNT(*)                   AS reviewed_orders,
       ROUND(CAST(AVG(so.review_score) AS NUMERIC), 2) AS avg_review,
       ROUND(CAST(100.0 * AVG(CASE WHEN so.delivery_status = 'Delayed' THEN 1.0 ELSE 0 END) AS NUMERIC), 2)
                                  AS delayed_pct
FROM (
    SELECT DISTINCT oi.seller_id, o.order_id, o.review_score, o.delivery_status
    FROM order_items oi
    JOIN order_features o ON o.order_id = oi.order_id
    WHERE {VALID} AND {FILTERS} AND o.review_score IS NOT NULL
) so
GROUP BY so.seller_id
HAVING COUNT(*) >= 30
ORDER BY avg_review ASC
LIMIT 15"""),

    "category_performance": ("Revenue, order value and rating by main category (50+ orders).", f"""
SELECT o.main_category                    AS category,
       COUNT(*)                           AS orders,
       ROUND(CAST(SUM(o.total_order_value) AS NUMERIC), 2) AS revenue,
       ROUND(CAST(AVG(o.total_order_value) AS NUMERIC), 2) AS avg_order_value,
       ROUND(CAST(AVG(o.review_score) AS NUMERIC), 2)      AS avg_review,
       ROUND(CAST(100.0 * AVG(CASE WHEN o.delivery_status = 'Delayed' THEN 1.0 ELSE 0 END) AS NUMERIC), 2)
                                          AS delayed_pct
FROM order_features o
WHERE {VALID} AND {FILTERS} AND o.main_category IS NOT NULL
GROUP BY o.main_category
HAVING COUNT(*) >= 50
ORDER BY revenue DESC"""),

    # ------------------------------------------------------- 5. Delivery analysis
    "delivery_kpis": ("Average delivery time and share of delayed orders.", f"""
SELECT ROUND(CAST(AVG(o.delivery_days) AS NUMERIC), 2)           AS avg_delivery_days,
       ROUND(CAST(AVG(o.estimated_delivery_days) AS NUMERIC), 2) AS avg_estimated_days,
       SUM(CASE WHEN o.delivery_status = 'On time' THEN 1 ELSE 0 END) AS on_time_orders,
       SUM(CASE WHEN o.delivery_status = 'Delayed' THEN 1 ELSE 0 END) AS delayed_orders,
       ROUND(CAST(100.0 * SUM(CASE WHEN o.delivery_status = 'Delayed' THEN 1 ELSE 0 END)
             / COUNT(*) AS NUMERIC), 2)                      AS delayed_pct
FROM order_features o
WHERE o.delivery_status IN ('On time', 'Delayed') AND {FILTERS}"""),

    "delivery_by_state": ("Delivery time, delay rate and rating by state (30+ deliveries).", f"""
SELECT o.customer_state                AS state,
       COUNT(*)                        AS delivered_orders,
       ROUND(CAST(AVG(o.delivery_days) AS NUMERIC), 2)  AS avg_delivery_days,
       ROUND(CAST(100.0 * AVG(CASE WHEN o.delivery_status = 'Delayed' THEN 1.0 ELSE 0 END) AS NUMERIC), 2)
                                       AS delayed_pct,
       ROUND(CAST(AVG(o.review_score) AS NUMERIC), 2)   AS avg_review
FROM order_features o
WHERE o.delivery_status IN ('On time', 'Delayed') AND {FILTERS}
GROUP BY o.customer_state
HAVING COUNT(*) >= 30
ORDER BY avg_delivery_days DESC"""),

    "delay_vs_review": ("Average review score by how early or late the order arrived.", f"""
WITH banded AS (
    SELECT o.review_score,
           CASE
               WHEN o.delivery_delay_days <= -8 THEN '1. 8+ days early'
               WHEN o.delivery_delay_days <= -1 THEN '2. 1-7 days early'
               WHEN o.delivery_delay_days = 0   THEN '3. On the day'
               WHEN o.delivery_delay_days <= 3  THEN '4. 1-3 days late'
               WHEN o.delivery_delay_days <= 7  THEN '5. 4-7 days late'
               ELSE '6. 8+ days late'
           END AS delay_band
    FROM order_features o
    WHERE o.delivery_status IN ('On time', 'Delayed')
      AND o.review_score IS NOT NULL AND {FILTERS}
)
SELECT delay_band, COUNT(*) AS orders, ROUND(CAST(AVG(review_score) AS NUMERIC), 2) AS avg_review
FROM banded
GROUP BY delay_band
ORDER BY delay_band"""),

    # ----------------------------------------------------- 6. Customer experience
    "review_distribution": ("Number and share of each review score.", f"""
SELECT o.review_score,
       COUNT(*) AS orders,
       ROUND(CAST(100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS NUMERIC), 2) AS pct
FROM order_features o
WHERE o.review_score IS NOT NULL AND {FILTERS}
GROUP BY o.review_score
ORDER BY o.review_score"""),

    "rating_vs_delivery": ("Review score and share of 1-2 star reviews by delivery status.", f"""
SELECT o.delivery_status,
       COUNT(*)                      AS orders,
       ROUND(CAST(AVG(o.review_score) AS NUMERIC), 2) AS avg_review,
       ROUND(CAST(100.0 * AVG(CASE WHEN o.review_score <= 2 THEN 1.0 ELSE 0 END) AS NUMERIC), 2) AS low_rating_pct
FROM order_features o
WHERE o.review_score IS NOT NULL AND {FILTERS}
GROUP BY o.delivery_status
ORDER BY avg_review DESC"""),
}


def run_query(engine: Engine, name: str, start_month: str, end_month: str,
              state: str = "All") -> pd.DataFrame:
    """Run a named query with the dashboard filters."""
    _, sql = QUERIES[name]
    params = {"start_month": start_month, "end_month": end_month, "state": state}
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn, params=params)
    return decimals_to_float(df)


def decimals_to_float(df: pd.DataFrame) -> pd.DataFrame:
    """PostgreSQL returns NUMERIC values as Python Decimal; turn them into floats
    so pandas, Plotly and the statistics code can do normal arithmetic on them."""
    for col in df.columns:
        if df[col].dtype == object and df[col].map(lambda v: isinstance(v, Decimal)).any():
            df[col] = pd.to_numeric(df[col].map(lambda v: float(v) if isinstance(v, Decimal) else v))
    return df


def export_queries(path=SQL_DIR / "business_queries.sql") -> None:
    """Write every query to a .sql file (filters shown as named parameters)."""
    parts = ["-- Cart2Insights business queries (generated from src/queries.py)",
             "-- Parameters: :start_month, :end_month ('YYYY-MM'), :state (code or 'All')", ""]
    for name, (description, sql) in QUERIES.items():
        parts += [f"-- {name}: {description}", sql.strip() + ";", ""]
    path.write_text("\n".join(parts))
