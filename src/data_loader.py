"""Step 3: find and load the 9 raw CSV files."""
import logging
from pathlib import Path

import pandas as pd

from src.config import RAW_DIR, TABLE_PATTERNS

log = logging.getLogger(__name__)

# Meaning of each column, used in the data dictionary. PK = primary key, FK = foreign key.
COLUMN_DESCRIPTIONS = {
    "customer_id": "Customer key for one order (PK in customers, FK in orders)",
    "customer_unique_id": "The real customer; the same person gets a new customer_id per order",
    "customer_zip_code_prefix": "First 5 digits of the customer's zip code",
    "customer_city": "Customer city", "customer_state": "Customer state (2-letter code)",
    "geolocation_zip_code_prefix": "Zip code prefix (repeats many times in the raw file)",
    "geolocation_lat": "Latitude", "geolocation_lng": "Longitude",
    "geolocation_city": "City", "geolocation_state": "State",
    "order_id": "Order key (PK in orders, FK in items, payments, reviews)",
    "order_status": "Order status: delivered, shipped, canceled, unavailable, ...",
    "order_purchase_timestamp": "When the order was placed",
    "order_approved_at": "When payment was approved",
    "order_delivered_carrier_date": "When the seller handed the order to the carrier",
    "order_delivered_customer_date": "When the customer received the order",
    "order_estimated_delivery_date": "Delivery date promised to the customer",
    "order_item_id": "Item number within the order (1, 2, 3 ...); PK with order_id",
    "product_id": "Product key (PK in products, FK in order_items)",
    "seller_id": "Seller key (PK in sellers, FK in order_items)",
    "shipping_limit_date": "Latest date the seller must ship the item",
    "price": "Item price (BRL)", "freight_value": "Shipping cost of the item (BRL)",
    "payment_sequential": "Payment number within the order; PK with order_id",
    "payment_type": "credit_card, boleto, voucher or debit_card",
    "payment_installments": "Number of instalments chosen",
    "payment_value": "Amount paid in this payment (BRL)",
    "review_id": "Review key", "review_score": "Rating from 1 to 5",
    "review_comment_title": "Review title (Portuguese)",
    "review_comment_message": "Review text (Portuguese)",
    "review_creation_date": "When the review survey was sent",
    "review_answer_timestamp": "When the customer answered",
    "product_category_name": "Category in Portuguese (FK to translation table)",
    "product_category_name_english": "Category in English",
    "product_name_lenght": "Characters in product name (misspelled in raw file)",
    "product_description_lenght": "Characters in description (misspelled in raw file)",
    "product_photos_qty": "Number of product photos", "product_weight_g": "Weight in grams",
    "product_length_cm": "Length in cm", "product_height_cm": "Height in cm",
    "product_width_cm": "Width in cm",
    "seller_zip_code_prefix": "First 5 digits of the seller's zip code",
    "seller_city": "Seller city", "seller_state": "Seller state (2-letter code)",
}


def find_table_files(raw_dir: Path = RAW_DIR) -> dict[str, Path]:
    """Map each logical table name to its CSV file in `raw_dir`."""
    raw_dir = Path(raw_dir)
    csv_files = sorted(raw_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in {raw_dir}. Download the dataset into this folder first."
        )

    mapping = {}
    for table, pattern in TABLE_PATTERNS.items():
        matches = [f for f in csv_files if pattern in f.stem.lower()]
        if not matches:
            raise FileNotFoundError(f"No file for table '{table}' (looked for '*{pattern}*.csv').")
        if len(matches) > 1:
            names = ", ".join(m.name for m in matches)
            raise ValueError(f"More than one file matches table '{table}': {names}")
        mapping[table] = matches[0]
    return mapping


def load_raw_tables(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    """Read every raw CSV into a DataFrame, keyed by table name."""
    tables = {}
    for table, path in find_table_files(raw_dir).items():
        tables[table] = pd.read_csv(path)
        log.info("Loaded %-22s %9d rows x %2d cols  (%s)", table, *tables[table].shape, path.name)
    return tables


def describe_tables(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per table: shape, memory use and column list."""
    rows = []
    for name, df in tables.items():
        rows.append({
            "table": name,
            "rows": len(df),
            "columns": df.shape[1],
            "memory_mb": round(df.memory_usage(deep=True).sum() / 1e6, 2),
            "column_names": ", ".join(df.columns),
        })
    return pd.DataFrame(rows)


def build_data_dictionary(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Column-level data dictionary: type, nulls, unique values and an example value."""
    rows = []
    for name, df in tables.items():
        for col in df.columns:
            non_null = df[col].dropna()
            rows.append({
                "table": name,
                "column": col,
                "description": COLUMN_DESCRIPTIONS.get(col, ""),
                "dtype": str(df[col].dtype),
                "null_count": int(df[col].isna().sum()),
                "unique_values": int(df[col].nunique()),
                "example": str(non_null.iloc[0])[:40] if len(non_null) else "",
            })
    return pd.DataFrame(rows)
