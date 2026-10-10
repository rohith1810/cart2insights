"""Step 7: feature engineering.

Builds three analysis tables:
  order_features    one row per order (value, delivery, review, payment, category)
  customer_features one row per real customer (customer_unique_id)
  seller_features   one row per seller with sales

Important: an order can have several item rows and several payment rows.
Items and payments are aggregated to order level *before* joining, otherwise
revenue would be counted more than once.
"""
import numpy as np
import pandas as pd

INVALID_STATUSES = ["canceled", "unavailable"]


def _order_level_items(items, products, translation) -> pd.DataFrame:
    agg = (items.groupby("order_id")
           .agg(items_count=("order_item_id", "count"),
                sellers_count=("seller_id", "nunique"),
                items_value=("price", "sum"),
                freight_value=("freight_value", "sum"))
           .reset_index())

    # Main category = category of the most expensive item in the order.
    cat = (items.merge(products[["product_id", "product_category_name"]], on="product_id", how="left")
           .merge(translation, on="product_category_name", how="left")
           .sort_values(["order_id", "price"], ascending=[True, False])
           .drop_duplicates("order_id"))
    cat = cat[["order_id", "product_category_name_english"]].rename(
        columns={"product_category_name_english": "main_category"})
    return agg.merge(cat, on="order_id", how="left")


def _order_level_payments(payments) -> pd.DataFrame:
    agg = (payments.groupby("order_id")
           .agg(payment_value=("payment_value", "sum"),
                payment_installments=("payment_installments", "max"))
           .reset_index())
    # Main payment type = the method that paid the largest share of the order.
    main = (payments.sort_values(["order_id", "payment_value"], ascending=[True, False])
            .drop_duplicates("order_id")[["order_id", "payment_type"]]
            .rename(columns={"payment_type": "main_payment_type"}))
    return agg.merge(main, on="order_id", how="left")


def build_order_features(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    df = (t["orders"]
          .merge(t["customers"][["customer_id", "customer_unique_id", "customer_state", "customer_city"]],
                 on="customer_id", how="left")
          .merge(_order_level_items(t["order_items"], t["products"], t["category_translation"]),
                 on="order_id", how="left")
          .merge(_order_level_payments(t["payments"]), on="order_id", how="left")
          .merge(t["reviews"][["order_id", "review_score"]], on="order_id", how="left"))

    purchase = df["order_purchase_timestamp"]
    delivered = df["order_delivered_customer_date"]
    estimated = df["order_estimated_delivery_date"]

    df["purchase_month"] = purchase.dt.strftime("%Y-%m")
    df["purchase_weekday"] = purchase.dt.day_name()
    df["purchase_hour"] = purchase.dt.hour

    df["total_order_value"] = (df["items_value"] + df["freight_value"]).round(2)

    df["delivery_days"] = ((delivered - purchase).dt.total_seconds() / 86400).round(2)
    df["estimated_delivery_days"] = ((estimated - purchase).dt.total_seconds() / 86400).round(2)
    # Compare calendar dates: delivered on the estimated day counts as on time.
    df["delivery_delay_days"] = (delivered.dt.normalize() - estimated.dt.normalize()).dt.days

    is_delivered = delivered.notna() & estimated.notna()
    df["delivery_status"] = np.select(
        [~is_delivered, df["delivery_delay_days"] > 0], ["Not delivered", "Delayed"], "On time")
    df["is_delayed"] = pd.Series(
        np.where(is_delivered, (df["delivery_delay_days"] > 0).astype(int), np.nan)).astype("Int64")

    df["is_valid_sale"] = (~df["order_status"].isin(INVALID_STATUSES)
                           & df["items_count"].notna()).astype(int)

    # Customer-level counts, based on valid sales only.
    counts = (df[df["is_valid_sale"] == 1].groupby("customer_unique_id")["order_id"]
              .nunique().rename("customer_order_count"))
    df = df.merge(counts, on="customer_unique_id", how="left")
    df["customer_order_count"] = df["customer_order_count"].fillna(0).astype(int)
    df["is_repeat_customer"] = (df["customer_order_count"] > 1).astype(int)

    for col in ["items_count", "sellers_count", "payment_installments", "review_score",
                "delivery_delay_days"]:
        df[col] = df[col].astype("Int64")
    return df


def build_customer_features(order_features: pd.DataFrame) -> pd.DataFrame:
    valid = order_features[order_features["is_valid_sale"] == 1]
    cust = (valid.sort_values("order_purchase_timestamp")
            .groupby("customer_unique_id")
            .agg(customer_state=("customer_state", "last"),
                 order_count=("order_id", "nunique"),
                 total_spend=("total_order_value", "sum"),
                 avg_review_score=("review_score", "mean"),
                 first_purchase=("order_purchase_timestamp", "min"),
                 last_purchase=("order_purchase_timestamp", "max"))
            .reset_index())
    cust["total_spend"] = cust["total_spend"].round(2)
    cust["avg_order_value"] = (cust["total_spend"] / cust["order_count"]).round(2)
    cust["avg_review_score"] = cust["avg_review_score"].astype(float).round(2)
    cust["is_repeat_customer"] = (cust["order_count"] > 1).astype(int)
    return cust


def build_seller_features(t: dict[str, pd.DataFrame], order_features: pd.DataFrame) -> pd.DataFrame:
    of = order_features[["order_id", "is_valid_sale", "review_score", "delivery_days", "is_delayed"]]
    items = t["order_items"].merge(of, on="order_id")
    items = items[items["is_valid_sale"] == 1]

    sales = (items.groupby("seller_id")
             .agg(order_count=("order_id", "nunique"),
                  items_sold=("order_item_id", "count"),
                  seller_revenue=("price", "sum"),
                  freight_total=("freight_value", "sum"),
                  avg_item_price=("price", "mean"))
             .reset_index())

    # Review and delivery are order-level facts: count each order once per seller.
    per_order = items.drop_duplicates(["seller_id", "order_id"])
    per_order = per_order.assign(review_score=per_order["review_score"].astype(float),
                                 is_delayed=per_order["is_delayed"].astype(float))
    quality = (per_order.groupby("seller_id")
               .agg(avg_review_score=("review_score", "mean"),
                    avg_delivery_days=("delivery_days", "mean"),
                    delayed_rate=("is_delayed", "mean"))
               .reset_index())

    sellers = sales.merge(quality, on="seller_id", how="left").merge(
        t["sellers"][["seller_id", "seller_state"]], on="seller_id", how="left")
    for col in ["seller_revenue", "freight_total", "avg_item_price", "avg_review_score",
                "avg_delivery_days"]:
        sellers[col] = sellers[col].round(2)
    sellers["delayed_rate"] = sellers["delayed_rate"].round(4)
    return sellers


def build_all_features(t: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    orders = build_order_features(t)
    return {
        "order_features": orders,
        "customer_features": build_customer_features(orders),
        "seller_features": build_seller_features(t, orders),
    }
