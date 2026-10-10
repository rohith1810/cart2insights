-- Cart2Insights schema for PostgreSQL (generated from src/db.py)
-- Create the database first (run once, e.g. in psql):
--   CREATE DATABASE cart2insights;
-- then connect to it:  \c cart2insights

CREATE TABLE category_translation (
	product_category_name VARCHAR(80) NOT NULL, 
	product_category_name_english VARCHAR(80) NOT NULL, 
	PRIMARY KEY (product_category_name)
);

CREATE TABLE customer_features (
	customer_unique_id VARCHAR(32) NOT NULL, 
	customer_state VARCHAR(2), 
	order_count INTEGER, 
	total_spend FLOAT, 
	avg_order_value FLOAT, 
	avg_review_score FLOAT, 
	first_purchase TIMESTAMP WITHOUT TIME ZONE, 
	last_purchase TIMESTAMP WITHOUT TIME ZONE, 
	is_repeat_customer INTEGER, 
	PRIMARY KEY (customer_unique_id)
);

CREATE TABLE customers (
	customer_id VARCHAR(32) NOT NULL, 
	customer_unique_id VARCHAR(32) NOT NULL, 
	customer_zip_code_prefix VARCHAR(5), 
	customer_city VARCHAR(100), 
	customer_state VARCHAR(2), 
	PRIMARY KEY (customer_id)
);
CREATE INDEX ix_customers_customer_state ON customers (customer_state);
CREATE INDEX ix_customers_customer_zip_code_prefix ON customers (customer_zip_code_prefix);
CREATE INDEX ix_customers_customer_unique_id ON customers (customer_unique_id);

CREATE TABLE geolocation (
	geolocation_zip_code_prefix VARCHAR(5) NOT NULL, 
	geolocation_lat FLOAT, 
	geolocation_lng FLOAT, 
	geolocation_city VARCHAR(100), 
	geolocation_state VARCHAR(2), 
	PRIMARY KEY (geolocation_zip_code_prefix)
);

CREATE TABLE sellers (
	seller_id VARCHAR(32) NOT NULL, 
	seller_zip_code_prefix VARCHAR(5), 
	seller_city VARCHAR(100), 
	seller_state VARCHAR(2), 
	PRIMARY KEY (seller_id)
);
CREATE INDEX ix_sellers_seller_state ON sellers (seller_state);
CREATE INDEX ix_sellers_seller_zip_code_prefix ON sellers (seller_zip_code_prefix);

CREATE TABLE orders (
	order_id VARCHAR(32) NOT NULL, 
	customer_id VARCHAR(32) NOT NULL, 
	order_status VARCHAR(20), 
	order_purchase_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	order_approved_at TIMESTAMP WITHOUT TIME ZONE, 
	order_delivered_carrier_date TIMESTAMP WITHOUT TIME ZONE, 
	order_delivered_customer_date TIMESTAMP WITHOUT TIME ZONE, 
	order_estimated_delivery_date TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (order_id), 
	FOREIGN KEY(customer_id) REFERENCES customers (customer_id)
);
CREATE INDEX ix_orders_customer_id ON orders (customer_id);
CREATE INDEX ix_orders_order_status ON orders (order_status);

CREATE TABLE products (
	product_id VARCHAR(32) NOT NULL, 
	product_category_name VARCHAR(80), 
	product_name_length INTEGER, 
	product_description_length INTEGER, 
	product_photos_qty INTEGER, 
	product_weight_g FLOAT, 
	product_length_cm FLOAT, 
	product_height_cm FLOAT, 
	product_width_cm FLOAT, 
	PRIMARY KEY (product_id), 
	FOREIGN KEY(product_category_name) REFERENCES category_translation (product_category_name)
);
CREATE INDEX ix_products_product_category_name ON products (product_category_name);

CREATE TABLE seller_features (
	seller_id VARCHAR(32) NOT NULL, 
	seller_state VARCHAR(2), 
	order_count INTEGER, 
	items_sold INTEGER, 
	seller_revenue FLOAT, 
	freight_total FLOAT, 
	avg_item_price FLOAT, 
	avg_review_score FLOAT, 
	avg_delivery_days FLOAT, 
	delayed_rate FLOAT, 
	PRIMARY KEY (seller_id), 
	FOREIGN KEY(seller_id) REFERENCES sellers (seller_id)
);

CREATE TABLE order_features (
	order_id VARCHAR(32) NOT NULL, 
	customer_id VARCHAR(32) NOT NULL, 
	customer_unique_id VARCHAR(32) NOT NULL, 
	customer_state VARCHAR(2), 
	customer_city VARCHAR(100), 
	order_status VARCHAR(20), 
	order_purchase_timestamp TIMESTAMP WITHOUT TIME ZONE, 
	purchase_month VARCHAR(7), 
	purchase_weekday VARCHAR(9), 
	purchase_hour INTEGER, 
	items_count INTEGER, 
	sellers_count INTEGER, 
	items_value FLOAT, 
	freight_value FLOAT, 
	total_order_value FLOAT, 
	payment_value FLOAT, 
	payment_installments INTEGER, 
	main_payment_type VARCHAR(20), 
	main_category VARCHAR(80), 
	review_score INTEGER, 
	delivery_days FLOAT, 
	estimated_delivery_days FLOAT, 
	delivery_delay_days INTEGER, 
	delivery_status VARCHAR(15), 
	is_delayed INTEGER, 
	is_valid_sale INTEGER, 
	customer_order_count INTEGER, 
	is_repeat_customer INTEGER, 
	PRIMARY KEY (order_id), 
	FOREIGN KEY(order_id) REFERENCES orders (order_id)
);
CREATE INDEX ix_order_features_delivery_status ON order_features (delivery_status);
CREATE INDEX ix_order_features_customer_unique_id ON order_features (customer_unique_id);
CREATE INDEX ix_order_features_purchase_month ON order_features (purchase_month);
CREATE INDEX ix_order_features_is_valid_sale ON order_features (is_valid_sale);
CREATE INDEX ix_order_features_customer_state ON order_features (customer_state);

CREATE TABLE order_items (
	order_id VARCHAR(32) NOT NULL, 
	order_item_id INTEGER NOT NULL, 
	product_id VARCHAR(32) NOT NULL, 
	seller_id VARCHAR(32) NOT NULL, 
	shipping_limit_date TIMESTAMP WITHOUT TIME ZONE, 
	price FLOAT NOT NULL, 
	freight_value FLOAT NOT NULL, 
	PRIMARY KEY (order_id, order_item_id), 
	FOREIGN KEY(order_id) REFERENCES orders (order_id), 
	FOREIGN KEY(product_id) REFERENCES products (product_id), 
	FOREIGN KEY(seller_id) REFERENCES sellers (seller_id)
);
CREATE INDEX ix_order_items_product_id ON order_items (product_id);
CREATE INDEX ix_order_items_seller_id ON order_items (seller_id);

CREATE TABLE payments (
	order_id VARCHAR(32) NOT NULL, 
	payment_sequential INTEGER NOT NULL, 
	payment_type VARCHAR(20), 
	payment_installments INTEGER, 
	payment_value FLOAT NOT NULL, 
	PRIMARY KEY (order_id, payment_sequential), 
	FOREIGN KEY(order_id) REFERENCES orders (order_id)
);
CREATE INDEX ix_payments_payment_type ON payments (payment_type);

CREATE TABLE reviews (
	review_id VARCHAR(32) NOT NULL, 
	order_id VARCHAR(32) NOT NULL, 
	review_score INTEGER NOT NULL, 
	review_comment_title TEXT, 
	review_comment_message TEXT, 
	has_comment INTEGER, 
	review_creation_date TIMESTAMP WITHOUT TIME ZONE, 
	review_answer_timestamp TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (review_id), 
	UNIQUE (order_id), 
	FOREIGN KEY(order_id) REFERENCES orders (order_id)
);
