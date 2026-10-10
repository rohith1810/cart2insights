"""Step 4: data quality analysis of the raw tables.

Checks: missing values, duplicate rows, primary-key uniqueness, data types,
invalid values and outliers (IQR rule). Nothing is changed here; the results
decide what the cleaning step must do.
"""
import pandas as pd

from src.config import PRIMARY_KEYS

DATE_COLUMNS = {
    "orders": [
        "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
    "reviews": ["review_creation_date", "review_answer_timestamp"],
}


def table_overview(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Missing cells, duplicate rows and duplicate primary keys per table."""
    rows = []
    for name, df in tables.items():
        pk = PRIMARY_KEYS.get(name)
        pk_dupes = int(df.duplicated(subset=pk).sum()) if pk else None
        rows.append({
            "table": name,
            "rows": len(df),
            "missing_cells": int(df.isna().sum().sum()),
            "missing_pct": round(100 * df.isna().sum().sum() / df.size, 2) if df.size else 0,
            "duplicate_rows": int(df.duplicated().sum()),
            "primary_key": ", ".join(pk) if pk else "none",
            "duplicate_keys": pk_dupes,
        })
    return pd.DataFrame(rows)


def missing_by_column(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Every column that has at least one missing value."""
    rows = []
    for name, df in tables.items():
        nulls = df.isna().sum()
        for col, n in nulls[nulls > 0].items():
            rows.append({"table": name, "column": col, "missing": int(n),
                         "missing_pct": round(100 * n / len(df), 2)})
    return pd.DataFrame(rows, columns=["table", "column", "missing", "missing_pct"])


def dtype_issues(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Date columns stored as text, and zip codes stored as numbers."""
    rows = []
    for name, cols in DATE_COLUMNS.items():
        for col in cols:
            if col in tables[name] and not pd.api.types.is_datetime64_any_dtype(tables[name][col]):
                rows.append({"table": name, "column": col,
                             "current_type": str(tables[name][col].dtype), "should_be": "datetime"})
    for name, df in tables.items():
        for col in df.columns:
            if "zip_code_prefix" in col and pd.api.types.is_numeric_dtype(df[col]):
                rows.append({"table": name, "column": col, "current_type": str(df[col].dtype),
                             "should_be": "5-character text (keeps leading zeros)"})
    return pd.DataFrame(rows, columns=["table", "column", "current_type", "should_be"])


def invalid_values(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Business-rule checks that raw data should pass."""
    t = tables
    orders = t["orders"].copy()
    for col in DATE_COLUMNS["orders"]:
        orders[col] = pd.to_datetime(orders[col], errors="coerce")

    checks = {
        ("order_items", "price <= 0"): (t["order_items"]["price"] <= 0).sum(),
        ("order_items", "freight_value < 0"): (t["order_items"]["freight_value"] < 0).sum(),
        ("payments", "payment_value < 0"): (t["payments"]["payment_value"] < 0).sum(),
        ("payments", "payment_type = 'not_defined'"):
            (t["payments"]["payment_type"] == "not_defined").sum(),
        ("payments", "payment_installments = 0"):
            (t["payments"]["payment_installments"] == 0).sum(),
        ("reviews", "review_score outside 1-5"):
            (~t["reviews"]["review_score"].between(1, 5)).sum(),
        ("reviews", "more than one review for an order"):
            t["reviews"].duplicated(subset="order_id").sum(),
        ("orders", "delivered before purchase"):
            (orders["order_delivered_customer_date"] < orders["order_purchase_timestamp"]).sum(),
        ("orders", "approved before purchase"):
            (orders["order_approved_at"] < orders["order_purchase_timestamp"]).sum(),
        ("orders", "status 'delivered' but no delivery date"):
            ((orders["order_status"] == "delivered")
             & orders["order_delivered_customer_date"].isna()).sum(),
        ("products", "missing category"): t["products"]["product_category_name"].isna().sum(),
        ("products", "category missing from translation table"):
            (~t["products"]["product_category_name"].dropna()
             .isin(t["category_translation"]["product_category_name"])).sum(),
        ("orders", "customer_id not in customers"):
            (~orders["customer_id"].isin(t["customers"]["customer_id"])).sum(),
        ("order_items", "order_id not in orders"):
            (~t["order_items"]["order_id"].isin(orders["order_id"])).sum(),
    }
    return pd.DataFrame(
        [{"table": k[0], "check": k[1], "failing_rows": int(v)} for k, v in checks.items()]
    )


def outlier_summary(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """IQR outlier counts for the key numeric columns (flagged, not removed)."""
    targets = {
        "order_items": ["price", "freight_value"],
        "payments": ["payment_value", "payment_installments"],
        "products": ["product_weight_g", "product_photos_qty"],
    }
    rows = []
    for name, cols in targets.items():
        for col in cols:
            s = tables[name][col].dropna()
            q1, q3 = s.quantile([0.25, 0.75])
            iqr = q3 - q1
            low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            rows.append({
                "table": name, "column": col, "min": round(s.min(), 2), "median": round(s.median(), 2),
                "max": round(s.max(), 2), "upper_fence": round(high, 2),
                "outliers": int(((s < low) | (s > high)).sum()),
                "outlier_pct": round(100 * ((s < low) | (s > high)).mean(), 2),
            })
    return pd.DataFrame(rows)


def run_quality_report(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Run every check and return the results by section name."""
    return {
        "Table overview": table_overview(tables),
        "Missing values by column": missing_by_column(tables),
        "Data type issues": dtype_issues(tables),
        "Invalid values": invalid_values(tables),
        "Outliers (IQR rule)": outlier_summary(tables),
    }
