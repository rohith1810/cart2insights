"""Step 5: data cleaning and preprocessing.

Each table has its own cleaning function so every decision is easy to find and
explain. `clean_all` runs them in dependency order (parents before children) and
drops child rows whose parent is missing, so the foreign keys in SQL will hold.

Outliers in price, freight and payment value are kept on purpose: they are real
expensive products, not data errors. They are flagged in the quality report.
"""
import logging

import pandas as pd

from src.data_quality import DATE_COLUMNS

log = logging.getLogger(__name__)

# Rough bounding box of Brazil, used to drop impossible geolocation points.
BRAZIL_LAT = (-34.0, 5.5)
BRAZIL_LNG = (-74.0, -34.0)


# ---------------------------------------------------------------- helpers
def normalize_text(s: pd.Series) -> pd.Series:
    """Lower-case, trim, remove accents and collapse spaces ("São Paulo " -> "sao paulo")."""
    s = s.astype("object")
    return (
        s.str.strip()
        .str.lower()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("ascii")
        .str.replace(r"\s+", " ", regex=True)
    )


def format_zip(s: pd.Series) -> pd.Series:
    """Zip prefixes as 5-character text so leading zeros are not lost (1001 -> '01001')."""
    return pd.to_numeric(s, errors="coerce").astype("Int64").astype("string").str.zfill(5)


def to_datetime(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for col in cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


# ------------------------------------------------------------ per table
def clean_customers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates().drop_duplicates(subset="customer_id").copy()
    df["customer_zip_code_prefix"] = format_zip(df["customer_zip_code_prefix"])
    df["customer_city"] = normalize_text(df["customer_city"])
    df["customer_state"] = df["customer_state"].astype("string").str.strip().str.upper()
    return df.dropna(subset=["customer_id", "customer_unique_id"])


def clean_geolocation(df: pd.DataFrame) -> pd.DataFrame:
    """Raw file repeats each zip many times. Keep one row per zip:
    mean latitude/longitude and the most frequent city/state."""
    df = df.drop_duplicates().copy()
    df = df[df["geolocation_lat"].between(*BRAZIL_LAT) & df["geolocation_lng"].between(*BRAZIL_LNG)]
    df["geolocation_zip_code_prefix"] = format_zip(df["geolocation_zip_code_prefix"])
    df["geolocation_city"] = normalize_text(df["geolocation_city"])
    df["geolocation_state"] = df["geolocation_state"].astype("string").str.strip().str.upper()

    coords = (df.groupby("geolocation_zip_code_prefix")[["geolocation_lat", "geolocation_lng"]]
              .mean().round(6).reset_index())
    place = (df.groupby(["geolocation_zip_code_prefix", "geolocation_city", "geolocation_state"])
             .size().reset_index(name="n")
             .sort_values(["geolocation_zip_code_prefix", "n"], ascending=[True, False])
             .drop_duplicates("geolocation_zip_code_prefix")
             .drop(columns="n"))
    return coords.merge(place, on="geolocation_zip_code_prefix", how="left")


def clean_sellers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates().drop_duplicates(subset="seller_id").copy()
    df["seller_zip_code_prefix"] = format_zip(df["seller_zip_code_prefix"])
    df["seller_city"] = normalize_text(df["seller_city"])
    df["seller_state"] = df["seller_state"].astype("string").str.strip().str.upper()
    return df.dropna(subset=["seller_id"])


def clean_products(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates().drop_duplicates(subset="product_id").copy()
    # Fix the misspelled column names in the raw file ("lenght").
    df = df.rename(columns={
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    })
    df["product_category_name"] = normalize_text(df["product_category_name"]).str.replace(" ", "_")
    df["product_category_name"] = df["product_category_name"].fillna("unknown")

    # Missing text lengths / photo counts mean "not provided" -> 0.
    for col in ["product_name_length", "product_description_length", "product_photos_qty"]:
        df[col] = df[col].fillna(0).astype(int)

    # Weight 0 is impossible; missing or zero dimensions get the category median,
    # then the overall median if the whole category is missing.
    dims = ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]
    for col in dims:
        df[col] = df[col].mask(df[col] <= 0)
        df[col] = df[col].fillna(df.groupby("product_category_name")[col].transform("median"))
        df[col] = df[col].fillna(df[col].median())
    return df


def clean_category_translation(df: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Normalise names and add any category used by products but missing here
    (its English name is the Portuguese name with underscores replaced)."""
    df = df.drop_duplicates().copy()
    df["product_category_name"] = normalize_text(df["product_category_name"]).str.replace(" ", "_")
    df["product_category_name_english"] = (
        normalize_text(df["product_category_name_english"]).str.replace(" ", "_"))
    df = df.dropna(subset=["product_category_name"]).drop_duplicates(subset="product_category_name")

    missing = sorted(set(products["product_category_name"]) - set(df["product_category_name"]))
    if missing:
        log.info("Adding %d categories missing from translation: %s", len(missing), missing)
        extra = pd.DataFrame({"product_category_name": missing,
                              "product_category_name_english": missing})
        df = pd.concat([df, extra], ignore_index=True)
    return df


def clean_orders(df: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates().drop_duplicates(subset="order_id").copy()
    df = to_datetime(df, DATE_COLUMNS["orders"])
    df["order_status"] = normalize_text(df["order_status"])

    df = df.dropna(subset=["order_purchase_timestamp"])
    # Dates earlier than the purchase are impossible: blank them rather than drop the order.
    for col in ["order_approved_at", "order_delivered_carrier_date", "order_delivered_customer_date"]:
        df.loc[df[col] < df["order_purchase_timestamp"], col] = pd.NaT
    return df[df["customer_id"].isin(customers["customer_id"])]


def clean_order_items(df, orders, products, sellers) -> pd.DataFrame:
    df = df.drop_duplicates().drop_duplicates(subset=["order_id", "order_item_id"]).copy()
    df = to_datetime(df, DATE_COLUMNS["order_items"])
    df = df[(df["price"] > 0) & (df["freight_value"] >= 0)]
    return df[df["order_id"].isin(orders["order_id"])
              & df["product_id"].isin(products["product_id"])
              & df["seller_id"].isin(sellers["seller_id"])]


def clean_payments(df: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates().drop_duplicates(subset=["order_id", "payment_sequential"]).copy()
    df["payment_type"] = normalize_text(df["payment_type"])
    df = df[(df["payment_type"] != "not_defined") & (df["payment_value"] >= 0)]
    # 0 installments is not possible; a single payment counts as 1.
    df["payment_installments"] = df["payment_installments"].clip(lower=1).astype(int)
    return df[df["order_id"].isin(orders["order_id"])]


def clean_reviews(df: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    """Keep one review per order: the most recently answered one."""
    df = df.drop_duplicates().copy()
    df = to_datetime(df, DATE_COLUMNS["reviews"])
    df = df[df["review_score"].between(1, 5)]
    df["review_score"] = df["review_score"].astype(int)
    df["review_comment_title"] = df["review_comment_title"].fillna("").astype(str).str.strip()
    df["review_comment_message"] = df["review_comment_message"].fillna("").astype(str).str.strip()
    df["has_comment"] = (df["review_comment_message"] != "").astype(int)

    df = (df.sort_values(["order_id", "review_answer_timestamp", "review_creation_date"])
            .drop_duplicates(subset="order_id", keep="last")
            .drop_duplicates(subset="review_id", keep="last"))
    return df[df["order_id"].isin(orders["order_id"])]


# ---------------------------------------------------------------- runner
def clean_all(raw: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Clean every table. Returns the clean tables and a before/after row log."""
    c = {}
    c["customers"] = clean_customers(raw["customers"])
    c["geolocation"] = clean_geolocation(raw["geolocation"])
    c["sellers"] = clean_sellers(raw["sellers"])
    c["products"] = clean_products(raw["products"])
    c["category_translation"] = clean_category_translation(raw["category_translation"], c["products"])
    c["orders"] = clean_orders(raw["orders"], c["customers"])
    c["order_items"] = clean_order_items(raw["order_items"], c["orders"], c["products"], c["sellers"])
    c["payments"] = clean_payments(raw["payments"], c["orders"])
    c["reviews"] = clean_reviews(raw["reviews"], c["orders"])

    c = {k: v.reset_index(drop=True) for k, v in c.items()}
    log_rows = [{"table": k, "rows_before": len(raw[k]), "rows_after": len(c[k]),
                 "rows_removed": len(raw[k]) - len(c[k])} for k in c]
    return c, pd.DataFrame(log_rows)
