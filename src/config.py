"""Project-wide configuration: folder paths, raw-file patterns and the database URL.

Credentials are never hard-coded. They are read from a `.env` file in the project
root (see `.env.example`). If no PostgreSQL settings are found, the project falls back
to a local SQLite file so the pipeline can still be tested end to end.
"""
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

RAW_DIR = Path(os.getenv("RAW_DATA_DIR", str(ROOT_DIR / "data" / "raw")))
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
REPORTS_DIR = ROOT_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
SQL_DIR = ROOT_DIR / "sql"

# A keyword that appears in each table's CSV file name (case-insensitive).
# Matches the standard Olist names, e.g. "olist_orders_dataset.csv", and also
# simpler names such as "orders.csv".
TABLE_PATTERNS = {
    "customers": "customer",
    "geolocation": "geolocation",
    "orders": "orders",
    "order_items": "order_item",
    "payments": "payment",
    "reviews": "review",
    "products": "products",
    "sellers": "seller",
    "category_translation": "translation",
}

# Primary key(s) of every raw table, taken from the ER diagram.
# Geolocation has no natural key in the raw file (zip codes repeat).
PRIMARY_KEYS = {
    "customers": ["customer_id"],
    "geolocation": None,
    "orders": ["order_id"],
    "order_items": ["order_id", "order_item_id"],
    "payments": ["order_id", "payment_sequential"],
    "reviews": ["review_id"],
    "products": ["product_id"],
    "sellers": ["seller_id"],
    "category_translation": ["product_category_name"],
}

ALPHA = 0.05  # significance level for all hypothesis tests


def get_database_url() -> str:
    """Build the SQLAlchemy URL from environment variables.

    Priority: DATABASE_URL > DB_USER/DB_PASSWORD/... (PostgreSQL) > local SQLite file.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    user = os.getenv("DB_USER")
    if user:
        password = quote_plus(os.getenv("DB_PASSWORD", ""))
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        name = os.getenv("DB_NAME", "cart2insights")
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"

    return f"sqlite:///{ROOT_DIR / 'data' / 'cart2insights.db'}"
