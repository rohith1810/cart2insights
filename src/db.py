"""Step 6: SQL database — connection, schema (from the ER diagram) and loading.

The schema is defined once with SQLAlchemy, which creates the tables with
primary and foreign keys on PostgreSQL (or SQLite for local testing) and can also
print the PostgreSQL DDL into `sql/schema.sql`.
"""
import logging

import pandas as pd
from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, MetaData, String, Table, Text,
    create_engine, event, inspect, text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.schema import CreateIndex, CreateTable

from src.config import SQL_DIR, get_database_url

log = logging.getLogger(__name__)
metadata = MetaData()

ID = String(32)  # Olist ids are 32-character hashes

# ------------------------------------------------------------ raw tables
Table("category_translation", metadata,
      Column("product_category_name", String(80), primary_key=True),
      Column("product_category_name_english", String(80), nullable=False))

Table("geolocation", metadata,
      Column("geolocation_zip_code_prefix", String(5), primary_key=True),
      Column("geolocation_lat", Float),
      Column("geolocation_lng", Float),
      Column("geolocation_city", String(100)),
      Column("geolocation_state", String(2)))

Table("customers", metadata,
      Column("customer_id", ID, primary_key=True),
      Column("customer_unique_id", ID, nullable=False, index=True),
      Column("customer_zip_code_prefix", String(5), index=True),
      Column("customer_city", String(100)),
      Column("customer_state", String(2), index=True))

Table("sellers", metadata,
      Column("seller_id", ID, primary_key=True),
      Column("seller_zip_code_prefix", String(5), index=True),
      Column("seller_city", String(100)),
      Column("seller_state", String(2), index=True))

Table("products", metadata,
      Column("product_id", ID, primary_key=True),
      Column("product_category_name", String(80),
             ForeignKey("category_translation.product_category_name"), index=True),
      Column("product_name_length", Integer),
      Column("product_description_length", Integer),
      Column("product_photos_qty", Integer),
      Column("product_weight_g", Float),
      Column("product_length_cm", Float),
      Column("product_height_cm", Float),
      Column("product_width_cm", Float))

Table("orders", metadata,
      Column("order_id", ID, primary_key=True),
      Column("customer_id", ID, ForeignKey("customers.customer_id"), nullable=False, index=True),
      Column("order_status", String(20), index=True),
      Column("order_purchase_timestamp", DateTime, nullable=False),
      Column("order_approved_at", DateTime),
      Column("order_delivered_carrier_date", DateTime),
      Column("order_delivered_customer_date", DateTime),
      Column("order_estimated_delivery_date", DateTime))

Table("order_items", metadata,
      Column("order_id", ID, ForeignKey("orders.order_id"), primary_key=True),
      Column("order_item_id", Integer, primary_key=True),
      Column("product_id", ID, ForeignKey("products.product_id"), nullable=False, index=True),
      Column("seller_id", ID, ForeignKey("sellers.seller_id"), nullable=False, index=True),
      Column("shipping_limit_date", DateTime),
      Column("price", Float, nullable=False),
      Column("freight_value", Float, nullable=False))

Table("payments", metadata,
      Column("order_id", ID, ForeignKey("orders.order_id"), primary_key=True),
      Column("payment_sequential", Integer, primary_key=True),
      Column("payment_type", String(20), index=True),
      Column("payment_installments", Integer),
      Column("payment_value", Float, nullable=False))

Table("reviews", metadata,
      Column("review_id", ID, primary_key=True),
      Column("order_id", ID, ForeignKey("orders.order_id"), nullable=False, unique=True),
      Column("review_score", Integer, nullable=False),
      Column("review_comment_title", Text),
      Column("review_comment_message", Text),
      Column("has_comment", Integer),
      Column("review_creation_date", DateTime),
      Column("review_answer_timestamp", DateTime))

# ------------------------------------------------------- feature tables
Table("order_features", metadata,
      Column("order_id", ID, ForeignKey("orders.order_id"), primary_key=True),
      Column("customer_id", ID, nullable=False),
      Column("customer_unique_id", ID, nullable=False, index=True),
      Column("customer_state", String(2), index=True),
      Column("customer_city", String(100)),
      Column("order_status", String(20)),
      Column("order_purchase_timestamp", DateTime),
      Column("purchase_month", String(7), index=True),
      Column("purchase_weekday", String(9)),
      Column("purchase_hour", Integer),
      Column("items_count", Integer),
      Column("sellers_count", Integer),
      Column("items_value", Float),
      Column("freight_value", Float),
      Column("total_order_value", Float),
      Column("payment_value", Float),
      Column("payment_installments", Integer),
      Column("main_payment_type", String(20)),
      Column("main_category", String(80)),
      Column("review_score", Integer),
      Column("delivery_days", Float),
      Column("estimated_delivery_days", Float),
      Column("delivery_delay_days", Integer),
      Column("delivery_status", String(15), index=True),
      Column("is_delayed", Integer),
      Column("is_valid_sale", Integer, index=True),
      Column("customer_order_count", Integer),
      Column("is_repeat_customer", Integer))

Table("customer_features", metadata,
      Column("customer_unique_id", ID, primary_key=True),
      Column("customer_state", String(2)),
      Column("order_count", Integer),
      Column("total_spend", Float),
      Column("avg_order_value", Float),
      Column("avg_review_score", Float),
      Column("first_purchase", DateTime),
      Column("last_purchase", DateTime),
      Column("is_repeat_customer", Integer))

Table("seller_features", metadata,
      Column("seller_id", ID, ForeignKey("sellers.seller_id"), primary_key=True),
      Column("seller_state", String(2)),
      Column("order_count", Integer),
      Column("items_sold", Integer),
      Column("seller_revenue", Float),
      Column("freight_total", Float),
      Column("avg_item_price", Float),
      Column("avg_review_score", Float),
      Column("avg_delivery_days", Float),
      Column("delayed_rate", Float))

RAW_TABLES = ["category_translation", "geolocation", "customers", "sellers", "products",
              "orders", "order_items", "payments", "reviews"]
FEATURE_TABLES = ["order_features", "customer_features", "seller_features"]


# ------------------------------------------------------------ connection
def _enable_sqlite_foreign_keys(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON")
    cur.close()


def create_database_if_missing(url: str) -> None:
    """On PostgreSQL, create the database itself if it does not exist yet.

    PostgreSQL has no CREATE DATABASE IF NOT EXISTS, so we connect to the default
    `postgres` maintenance database, check pg_database, and create it if missing.
    CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT.
    """
    u = make_url(url)
    if u.get_backend_name() != "postgresql" or not u.database:
        return
    server_url = u.set(database="postgres")  # same server, maintenance database
    server = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"),
                              {"name": u.database}).scalar()
        if not exists:
            safe_name = u.database.replace('"', '""')
            conn.execute(text(f'CREATE DATABASE "{safe_name}" ENCODING \'UTF8\''))
            log.info("Created database %s", u.database)
    server.dispose()


def get_engine(url: str | None = None) -> Engine:
    url = url or get_database_url()
    create_database_if_missing(url)
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    log.info("Connected to %s database", engine.dialect.name)
    return engine


# --------------------------------------------------------------- loading
def reset_schema(engine: Engine) -> None:
    """Drop and re-create every table (children dropped first, parents created first)."""
    metadata.drop_all(engine)
    metadata.create_all(engine)


def load_table(engine: Engine, name: str, df: pd.DataFrame) -> None:
    """Append a DataFrame into an existing table, in the table's column order."""
    cols = [c.name for c in metadata.tables[name].columns]
    missing = set(cols) - set(df.columns)
    if missing:
        raise KeyError(f"{name}: DataFrame is missing columns {sorted(missing)}")
    chunk = max(1, 15000 // len(cols))  # stay under driver placeholder limits
    df[cols].to_sql(name, engine, if_exists="append", index=False, chunksize=chunk, method="multi")
    log.info("Loaded %-22s %9d rows", name, len(df))


def load_tables(engine: Engine, tables: dict[str, pd.DataFrame], order: list[str]) -> None:
    for name in order:
        load_table(engine, name, tables[name])


def verify_counts(engine: Engine, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Compare row counts in the database with the DataFrames that were loaded."""
    rows = []
    with engine.connect() as conn:
        for name, df in tables.items():
            n = conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar()
            rows.append({"table": name, "dataframe_rows": len(df), "database_rows": n,
                         "match": n == len(df)})
    return pd.DataFrame(rows)


def tables_exist(engine: Engine, names: list[str]) -> bool:
    existing = set(inspect(engine).get_table_names())
    return all(n in existing for n in names)


def export_postgres_schema(path=SQL_DIR / "schema.sql") -> None:
    """Write the PostgreSQL CREATE TABLE statements (with keys and indexes) to a .sql file."""
    dialect = postgresql.dialect()
    parts = ["-- Cart2Insights schema for PostgreSQL (generated from src/db.py)",
             "-- Create the database first (run once, e.g. in psql):",
             "--   CREATE DATABASE cart2insights;",
             "-- then connect to it:  \\c cart2insights", ""]
    for table in metadata.sorted_tables:
        parts.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
        for idx in table.indexes:
            parts.append(str(CreateIndex(idx).compile(dialect=dialect)).strip() + ";")
        parts.append("")
    path.write_text("\n".join(parts))
