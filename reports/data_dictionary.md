# Data dictionary

## Tables

| table                |    rows |   columns |   memory_mb | column_names                                                                                                                                                                     |
|:---------------------|--------:|----------:|------------:|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| customers            |   99441 |         5 |       11.57 | customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state                                                                                         |
| geolocation          | 1000163 |         5 |       52.56 | geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state                                                                               |
| orders               |   99441 |         8 |       23.01 | order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at, order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date     |
| order_items          |  112650 |         7 |       19.26 | order_id, order_item_id, product_id, seller_id, shipping_limit_date, price, freight_value                                                                                        |
| payments             |  103886 |         5 |        8.5  | order_id, payment_sequential, payment_type, payment_installments, payment_value                                                                                                  |
| reviews              |   99224 |         7 |       18.71 | review_id, order_id, review_score, review_comment_title, review_comment_message, review_creation_date, review_answer_timestamp                                                   |
| products             |   32951 |         9 |        3.91 | product_id, product_category_name, product_name_lenght, product_description_lenght, product_photos_qty, product_weight_g, product_length_cm, product_height_cm, product_width_cm |
| sellers              |    3095 |         4 |        0.24 | seller_id, seller_zip_code_prefix, seller_city, seller_state                                                                                                                     |
| category_translation |      71 |         2 |        0    | product_category_name, product_category_name_english                                                                                                                             |

## Columns

| table                | column                        | description                                                         | dtype   |   null_count |   unique_values | example                               |
|:---------------------|:------------------------------|:--------------------------------------------------------------------|:--------|-------------:|----------------:|:--------------------------------------|
| customers            | customer_id                   | Customer key for one order (PK in customers, FK in orders)          | str     |            0 |           99441 | 06b8999e2fba1a1fbc88172c00ba8bc7      |
| customers            | customer_unique_id            | The real customer; the same person gets a new customer_id per order | str     |            0 |           96096 | 861eff4711a542e4b93843c6dd7febb0      |
| customers            | customer_zip_code_prefix      | First 5 digits of the customer's zip code                           | int64   |            0 |           14994 | 14409                                 |
| customers            | customer_city                 | Customer city                                                       | str     |            0 |            4119 | franca                                |
| customers            | customer_state                | Customer state (2-letter code)                                      | str     |            0 |              27 | SP                                    |
| geolocation          | geolocation_zip_code_prefix   | Zip code prefix (repeats many times in the raw file)                | int64   |            0 |           19015 | 1037                                  |
| geolocation          | geolocation_lat               | Latitude                                                            | float64 |            0 |          717360 | -23.54562128115268                    |
| geolocation          | geolocation_lng               | Longitude                                                           | float64 |            0 |          717613 | -46.63929204800168                    |
| geolocation          | geolocation_city              | City                                                                | str     |            0 |            8011 | sao paulo                             |
| geolocation          | geolocation_state             | State                                                               | str     |            0 |              27 | SP                                    |
| orders               | order_id                      | Order key (PK in orders, FK in items, payments, reviews)            | str     |            0 |           99441 | e481f51cbdc54678b7cc49136f2d6af7      |
| orders               | customer_id                   | Customer key for one order (PK in customers, FK in orders)          | str     |            0 |           99441 | 9ef432eb6251297304e76186b10a928d      |
| orders               | order_status                  | Order status: delivered, shipped, canceled, unavailable, ...        | str     |            0 |               8 | delivered                             |
| orders               | order_purchase_timestamp      | When the order was placed                                           | str     |            0 |           98875 | 2017-10-02 10:56:33                   |
| orders               | order_approved_at             | When payment was approved                                           | str     |          160 |           90733 | 2017-10-02 11:07:15                   |
| orders               | order_delivered_carrier_date  | When the seller handed the order to the carrier                     | str     |         1783 |           81018 | 2017-10-04 19:55:00                   |
| orders               | order_delivered_customer_date | When the customer received the order                                | str     |         2965 |           95664 | 2017-10-10 21:25:13                   |
| orders               | order_estimated_delivery_date | Delivery date promised to the customer                              | str     |            0 |             459 | 2017-10-18 00:00:00                   |
| order_items          | order_id                      | Order key (PK in orders, FK in items, payments, reviews)            | str     |            0 |           98666 | 00010242fe8c5a6d1ba2dd792cb16214      |
| order_items          | order_item_id                 | Item number within the order (1, 2, 3 ...); PK with order_id        | int64   |            0 |              21 | 1                                     |
| order_items          | product_id                    | Product key (PK in products, FK in order_items)                     | str     |            0 |           32951 | 4244733e06e7ecb4970a6e2683c13e61      |
| order_items          | seller_id                     | Seller key (PK in sellers, FK in order_items)                       | str     |            0 |            3095 | 48436dade18ac8b2bce089ec2a041202      |
| order_items          | shipping_limit_date           | Latest date the seller must ship the item                           | str     |            0 |           93318 | 2017-09-19 09:45:35                   |
| order_items          | price                         | Item price (BRL)                                                    | float64 |            0 |            5968 | 58.9                                  |
| order_items          | freight_value                 | Shipping cost of the item (BRL)                                     | float64 |            0 |            6999 | 13.29                                 |
| payments             | order_id                      | Order key (PK in orders, FK in items, payments, reviews)            | str     |            0 |           99440 | b81ef226f3fe1789b1e8b2acac839d17      |
| payments             | payment_sequential            | Payment number within the order; PK with order_id                   | int64   |            0 |              29 | 1                                     |
| payments             | payment_type                  | credit_card, boleto, voucher or debit_card                          | str     |            0 |               5 | credit_card                           |
| payments             | payment_installments          | Number of instalments chosen                                        | int64   |            0 |              24 | 8                                     |
| payments             | payment_value                 | Amount paid in this payment (BRL)                                   | float64 |            0 |           29077 | 99.33                                 |
| reviews              | review_id                     | Review key                                                          | str     |            0 |           98410 | 7bc2406110b926393aa56f80a40eba40      |
| reviews              | order_id                      | Order key (PK in orders, FK in items, payments, reviews)            | str     |            0 |           98673 | 73fc7af87114b39712e6da79b0a377eb      |
| reviews              | review_score                  | Rating from 1 to 5                                                  | int64   |            0 |               5 | 4                                     |
| reviews              | review_comment_title          | Review title (Portuguese)                                           | str     |        87656 |            4527 | recomendo                             |
| reviews              | review_comment_message        | Review text (Portuguese)                                            | str     |        58247 |           36159 | Recebi bem antes do prazo estipulado. |
| reviews              | review_creation_date          | When the review survey was sent                                     | str     |            0 |             636 | 2018-01-18 00:00:00                   |
| reviews              | review_answer_timestamp       | When the customer answered                                          | str     |            0 |           98248 | 2018-01-18 21:46:59                   |
| products             | product_id                    | Product key (PK in products, FK in order_items)                     | str     |            0 |           32951 | 1e9e8ef04dbcff4541ed26657ea517e5      |
| products             | product_category_name         | Category in Portuguese (FK to translation table)                    | str     |          610 |              73 | perfumaria                            |
| products             | product_name_lenght           | Characters in product name (misspelled in raw file)                 | float64 |          610 |              66 | 40.0                                  |
| products             | product_description_lenght    | Characters in description (misspelled in raw file)                  | float64 |          610 |            2960 | 287.0                                 |
| products             | product_photos_qty            | Number of product photos                                            | float64 |          610 |              19 | 1.0                                   |
| products             | product_weight_g              | Weight in grams                                                     | float64 |            2 |            2204 | 225.0                                 |
| products             | product_length_cm             | Length in cm                                                        | float64 |            2 |              99 | 16.0                                  |
| products             | product_height_cm             | Height in cm                                                        | float64 |            2 |             102 | 10.0                                  |
| products             | product_width_cm              | Width in cm                                                         | float64 |            2 |              95 | 14.0                                  |
| sellers              | seller_id                     | Seller key (PK in sellers, FK in order_items)                       | str     |            0 |            3095 | 3442f8959a84dea7ee197c632cb2df15      |
| sellers              | seller_zip_code_prefix        | First 5 digits of the seller's zip code                             | int64   |            0 |            2246 | 13023                                 |
| sellers              | seller_city                   | Seller city                                                         | str     |            0 |             611 | campinas                              |
| sellers              | seller_state                  | Seller state (2-letter code)                                        | str     |            0 |              23 | SP                                    |
| category_translation | product_category_name         | Category in Portuguese (FK to translation table)                    | str     |            0 |              71 | beleza_saude                          |
| category_translation | product_category_name_english | Category in English                                                 | str     |            0 |              71 | health_beauty                         |
