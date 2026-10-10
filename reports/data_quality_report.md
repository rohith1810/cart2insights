# Data quality report (raw data)

## Table overview

| table                |    rows |   missing_cells |   missing_pct |   duplicate_rows | primary_key                  |   duplicate_keys |
|:---------------------|--------:|----------------:|--------------:|-----------------:|:-----------------------------|-----------------:|
| customers            |   99441 |               0 |          0    |                0 | customer_id                  |                0 |
| geolocation          | 1000163 |               0 |          0    |           261831 | none                         |              nan |
| orders               |   99441 |            4908 |          0.62 |                0 | order_id                     |                0 |
| order_items          |  112650 |               0 |          0    |                0 | order_id, order_item_id      |                0 |
| payments             |  103886 |               0 |          0    |                0 | order_id, payment_sequential |                0 |
| reviews              |   99224 |          145903 |         21.01 |                0 | review_id                    |              814 |
| products             |   32951 |            2448 |          0.83 |                0 | product_id                   |                0 |
| sellers              |    3095 |               0 |          0    |                0 | seller_id                    |                0 |
| category_translation |      71 |               0 |          0    |                0 | product_category_name        |                0 |

## Missing values by column

| table    | column                        |   missing |   missing_pct |
|:---------|:------------------------------|----------:|--------------:|
| orders   | order_approved_at             |       160 |          0.16 |
| orders   | order_delivered_carrier_date  |      1783 |          1.79 |
| orders   | order_delivered_customer_date |      2965 |          2.98 |
| reviews  | review_comment_title          |     87656 |         88.34 |
| reviews  | review_comment_message        |     58247 |         58.7  |
| products | product_category_name         |       610 |          1.85 |
| products | product_name_lenght           |       610 |          1.85 |
| products | product_description_lenght    |       610 |          1.85 |
| products | product_photos_qty            |       610 |          1.85 |
| products | product_weight_g              |         2 |          0.01 |
| products | product_length_cm             |         2 |          0.01 |
| products | product_height_cm             |         2 |          0.01 |
| products | product_width_cm              |         2 |          0.01 |

## Data type issues

| table       | column                        | current_type   | should_be                              |
|:------------|:------------------------------|:---------------|:---------------------------------------|
| orders      | order_purchase_timestamp      | str            | datetime                               |
| orders      | order_approved_at             | str            | datetime                               |
| orders      | order_delivered_carrier_date  | str            | datetime                               |
| orders      | order_delivered_customer_date | str            | datetime                               |
| orders      | order_estimated_delivery_date | str            | datetime                               |
| order_items | shipping_limit_date           | str            | datetime                               |
| reviews     | review_creation_date          | str            | datetime                               |
| reviews     | review_answer_timestamp       | str            | datetime                               |
| customers   | customer_zip_code_prefix      | int64          | 5-character text (keeps leading zeros) |
| geolocation | geolocation_zip_code_prefix   | int64          | 5-character text (keeps leading zeros) |
| sellers     | seller_zip_code_prefix        | int64          | 5-character text (keeps leading zeros) |

## Invalid values

| table       | check                                   |   failing_rows |
|:------------|:----------------------------------------|---------------:|
| order_items | price <= 0                              |              0 |
| order_items | freight_value < 0                       |              0 |
| payments    | payment_value < 0                       |              0 |
| payments    | payment_type = 'not_defined'            |              3 |
| payments    | payment_installments = 0                |              2 |
| reviews     | review_score outside 1-5                |              0 |
| reviews     | more than one review for an order       |            551 |
| orders      | delivered before purchase               |              0 |
| orders      | approved before purchase                |              0 |
| orders      | status 'delivered' but no delivery date |              8 |
| products    | missing category                        |            610 |
| products    | category missing from translation table |             13 |
| orders      | customer_id not in customers            |              0 |
| order_items | order_id not in orders                  |              0 |

## Outliers (IQR rule)

| table       | column               |   min |   median |      max |   upper_fence |   outliers |   outlier_pct |
|:------------|:---------------------|------:|---------:|---------:|--------------:|-----------:|--------------:|
| order_items | price                |  0.85 |    74.99 |  6735    |        277.4  |       8427 |          7.48 |
| order_items | freight_value        |  0    |    16.26 |   409.68 |         33.25 |      12134 |         10.77 |
| payments    | payment_value        |  0    |   100    | 13664.1  |        344.41 |       7981 |          7.68 |
| payments    | payment_installments |  0    |     1    |    24    |          8.5  |       6313 |          6.08 |
| products    | product_weight_g     |  0    |   700    | 40425    |       4300    |       4551 |         13.81 |
| products    | product_photos_qty   |  1    |     1    |    20    |          6    |        849 |          2.63 |
