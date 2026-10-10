"""Create a small synthetic dataset with the same 9 tables and columns as the real one.

Use it only to test that the code runs before the real data is downloaded:

    python scripts/make_sample_data.py
    python run_pipeline.py --raw-dir data/sample

The numbers are random, so never present results from this sample.
It deliberately includes dirty data (duplicates, nulls, invalid values) so the
cleaning step has something to do.
"""
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
OUT = Path(__file__).resolve().parents[1] / "data" / "sample"

STATES = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "GO", "ES", "PE", "CE", "PA", "MT", "AM"]
STATE_W = np.array([42, 13, 12, 5.5, 5, 3.7, 3.4, 2.2, 2, 2, 1.7, 1.3, 1, 0.9, 0.5])
CITIES = {"SP": "sao paulo", "RJ": "rio de janeiro", "MG": "belo horizonte", "RS": "porto alegre",
          "PR": "curitiba", "SC": "florianopolis", "BA": "salvador", "DF": "brasilia",
          "GO": "goiania", "ES": "vitoria", "PE": "recife", "CE": "fortaleza", "PA": "belem",
          "MT": "cuiaba", "AM": "manaus"}
DISTANCE = {s: i for i, s in enumerate(STATES)}  # further down the list = further from SP
CATEGORIES = {
    "cama_mesa_banho": ("bed_bath_table", 90), "beleza_saude": ("health_beauty", 130),
    "esporte_lazer": ("sports_leisure", 110), "moveis_decoracao": ("furniture_decor", 120),
    "informatica_acessorios": ("computers_accessories", 150), "utilidades_domesticas": ("housewares", 85),
    "relogios_presentes": ("watches_gifts", 200), "telefonia": ("telephony", 70),
    "automotivo": ("auto", 140), "brinquedos": ("toys", 115), "ferramentas_jardim": ("garden_tools", 105),
    "cool_stuff": ("cool_stuff", 170), "perfumaria": ("perfumery", 125), "bebes": ("baby", 130),
    "eletronicos": ("electronics", 95), "pc_gamer": (None, 400),  # missing from translation on purpose
}


def uid(prefix: str, i: int) -> str:
    return hashlib.md5(f"{prefix}{i}".encode()).hexdigest()


def main(n_customers=4000, n_sellers=180, n_products=600) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p_state = STATE_W / STATE_W.sum()

    # customers: some people order more than once -> same unique id, new customer_id
    uniq = [uid("u", i) for i in range(n_customers)]
    n_orders = int(n_customers * 1.08)
    cust_unique = np.concatenate([uniq, rng.choice(uniq, n_orders - n_customers)])
    cust_state = {u: rng.choice(STATES, p=p_state) for u in uniq}
    customers = pd.DataFrame({
        "customer_id": [uid("c", i) for i in range(n_orders)],
        "customer_unique_id": cust_unique,
        "customer_zip_code_prefix": rng.integers(1000, 99999, n_orders),
        "customer_state": [cust_state[u] for u in cust_unique],
    })
    customers["customer_city"] = customers["customer_state"].map(CITIES)
    customers.loc[customers.sample(frac=0.05, random_state=1).index, "customer_city"] = "São Paulo "
    customers = customers[["customer_id", "customer_unique_id", "customer_zip_code_prefix",
                           "customer_city", "customer_state"]]

    zips = pd.concat([customers["customer_zip_code_prefix"], pd.Series(rng.integers(1000, 99999, 300))])
    geo = pd.DataFrame({"geolocation_zip_code_prefix": np.repeat(zips.values, 3)})
    geo["geolocation_lat"] = rng.uniform(-30, -3, len(geo))
    geo["geolocation_lng"] = rng.uniform(-60, -35, len(geo))
    geo["geolocation_state"] = rng.choice(STATES, len(geo), p=p_state)
    geo["geolocation_city"] = geo["geolocation_state"].map(CITIES)
    geo.loc[:5, "geolocation_lat"] = 45.0  # impossible point

    sellers = pd.DataFrame({
        "seller_id": [uid("s", i) for i in range(n_sellers)],
        "seller_zip_code_prefix": rng.integers(1000, 99999, n_sellers),
        "seller_state": rng.choice(STATES[:6], n_sellers, p=[.6, .1, .12, .06, .07, .05]),
    })
    sellers["seller_city"] = sellers["seller_state"].map(CITIES)
    sellers = sellers[["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"]]
    seller_w = rng.pareto(1.2, n_sellers) + 0.05
    seller_w /= seller_w.sum()
    seller_speed = rng.normal(0, 2, n_sellers)

    cats = list(CATEGORIES)
    products = pd.DataFrame({
        "product_id": [uid("p", i) for i in range(n_products)],
        "product_category_name": rng.choice(cats, n_products),
        "product_name_lenght": rng.integers(10, 70, n_products).astype(float),
        "product_description_lenght": rng.integers(50, 3000, n_products).astype(float),
        "product_photos_qty": rng.integers(1, 8, n_products).astype(float),
        "product_weight_g": rng.integers(100, 20000, n_products).astype(float),
        "product_length_cm": rng.integers(10, 100, n_products).astype(float),
        "product_height_cm": rng.integers(2, 80, n_products).astype(float),
        "product_width_cm": rng.integers(8, 90, n_products).astype(float),
    })
    miss = products.sample(frac=0.02, random_state=2).index
    products.loc[miss, ["product_category_name", "product_name_lenght",
                        "product_description_lenght", "product_photos_qty"]] = np.nan
    products.loc[products.sample(5, random_state=3).index, "product_weight_g"] = 0
    base_price = products["product_category_name"].map(lambda c: CATEGORIES.get(c, ("", 100))[1])

    translation = pd.DataFrame([(k, v[0]) for k, v in CATEGORIES.items() if v[0]],
                               columns=["product_category_name", "product_category_name_english"])

    # orders
    purchase = pd.Timestamp("2017-01-01") + pd.to_timedelta(
        np.sort(rng.beta(2.2, 1.4, n_orders)) * 600 * 86400, unit="s")
    purchase = pd.Series(purchase).sample(frac=1, random_state=4).reset_index(drop=True)
    dist = customers["customer_state"].map(DISTANCE).values
    est_days = rng.integers(15, 35, n_orders) + dist // 2
    status = rng.choice(["delivered", "shipped", "canceled", "unavailable", "invoiced", "processing"],
                        n_orders, p=[.95, .018, .012, .007, .007, .006])
    orders = pd.DataFrame({"order_id": [uid("o", i) for i in range(n_orders)],
                           "customer_id": customers["customer_id"], "order_status": status,
                           "order_purchase_timestamp": purchase})
    orders["order_approved_at"] = purchase + pd.to_timedelta(rng.exponential(0.5, n_orders), unit="D")
    orders["order_delivered_carrier_date"] = purchase + pd.to_timedelta(
        rng.gamma(2, 1.5, n_orders), unit="D")

    # items (needed before delivery time, which depends on the seller)
    n_items = rng.choice([1, 1, 1, 1, 2, 2, 3], n_orders)
    rows = []
    for oid, k, ts in zip(orders["order_id"], n_items, purchase):
        seller = rng.choice(n_sellers, p=seller_w)
        for j in range(1, k + 1):
            pidx = rng.integers(n_products)
            price = round(float(base_price.iloc[pidx] * rng.lognormal(0, 0.6)), 2)
            rows.append((oid, j, products["product_id"].iloc[pidx], sellers["seller_id"].iloc[seller],
                         ts + pd.Timedelta(days=6), price, round(price * rng.uniform(.08, .3), 2),
                         seller))
    items = pd.DataFrame(rows, columns=["order_id", "order_item_id", "product_id", "seller_id",
                                        "shipping_limit_date", "price", "freight_value", "_seller"])
    first_seller = items.drop_duplicates("order_id").set_index("order_id")["_seller"]
    items = items.drop(columns="_seller")

    speed = seller_speed[first_seller.reindex(orders["order_id"]).values]
    deliver_days = np.clip(rng.gamma(3, 3.5, n_orders) + dist * 0.8 + speed, 1, None)
    orders["order_delivered_customer_date"] = purchase + pd.to_timedelta(deliver_days, unit="D")
    orders["order_estimated_delivery_date"] = (purchase + pd.to_timedelta(est_days, unit="D")).dt.normalize()
    not_done = orders["order_status"] != "delivered"
    orders.loc[not_done, "order_delivered_customer_date"] = pd.NaT
    orders.loc[orders.sample(8, random_state=5).index, "order_delivered_customer_date"] = pd.NaT
    items = items[~items["order_id"].isin(orders.loc[orders["order_status"] == "unavailable", "order_id"])]

    # payments
    totals = items.groupby("order_id").apply(lambda g: (g["price"] + g["freight_value"]).sum(),
                                             include_groups=False)
    pay_rows = []
    for oid, total in totals.items():
        ptype = rng.choice(["credit_card", "boleto", "voucher", "debit_card"], p=[.74, .19, .05, .02])
        if ptype == "voucher" and rng.random() < .5:
            part = round(total * .3, 2)
            pay_rows += [(oid, 1, "voucher", 1, part), (oid, 2, "credit_card", 3, round(total - part, 2))]
        else:
            inst = int(rng.integers(1, 10)) if ptype == "credit_card" else 1
            pay_rows.append((oid, 1, ptype, inst, round(total, 2)))
    payments = pd.DataFrame(pay_rows, columns=["order_id", "payment_sequential", "payment_type",
                                               "payment_installments", "payment_value"])
    payments.loc[payments.sample(3, random_state=6).index, "payment_type"] = "not_defined"
    payments.loc[payments.sample(2, random_state=7).index, "payment_installments"] = 0

    # reviews: score drops with lateness
    o = orders.set_index("order_id")
    late = (o["order_delivered_customer_date"].dt.normalize() - o["order_estimated_delivery_date"]).dt.days
    base = np.where(late.fillna(0) > 0, 2.6 - 0.05 * late.clip(0, 20), 4.35)
    base = np.where(o["order_status"].isin(["canceled", "unavailable"]), 1.8, base)
    score = np.clip(np.round(base + rng.normal(0, 1.1, len(o))), 1, 5).astype(int)
    created = o["order_estimated_delivery_date"].fillna(o["order_purchase_timestamp"]) + pd.Timedelta(days=1)
    reviews = pd.DataFrame({
        "review_id": [uid("r", i) for i in range(len(o))], "order_id": o.index, "review_score": score,
        "review_comment_title": np.where(rng.random(len(o)) < .1, "recomendo", None),
        "review_comment_message": np.where(rng.random(len(o)) < .4, "produto chegou", None),
        "review_creation_date": created,
        "review_answer_timestamp": created + pd.to_timedelta(rng.exponential(2, len(o)), unit="D"),
    }).sample(frac=0.99, random_state=8)
    extra = reviews.sample(40, random_state=9).assign(
        review_id=lambda d: [uid("rx", i) for i in range(len(d))],
        review_answer_timestamp=lambda d: d["review_answer_timestamp"] + pd.Timedelta(days=3))
    reviews = pd.concat([reviews, extra])

    # a few exact duplicate rows
    customers = pd.concat([customers, customers.sample(10, random_state=10)])
    items = pd.concat([items, items.sample(10, random_state=11)])

    files = {"olist_customers_dataset": customers, "olist_geolocation_dataset": geo,
             "olist_orders_dataset": orders, "olist_order_items_dataset": items,
             "olist_order_payments_dataset": payments, "olist_order_reviews_dataset": reviews,
             "olist_products_dataset": products, "olist_sellers_dataset": sellers,
             "product_category_name_translation": translation}
    for name, df in files.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name:40s} {len(df):7d} rows")
    print(f"Sample data written to {OUT}")


if __name__ == "__main__":
    main()
