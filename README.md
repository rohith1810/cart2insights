# Cart2Insights: Decoding E-Commerce Performance

An end-to-end analytics project on a 9-table e-commerce dataset (orders, items, payments,
reviews, customers, sellers, products, geolocation, category translation). Raw CSVs are
cleaned with Pandas, stored in PostgreSQL with primary and foreign keys, enriched with business
features, explored with EDA and hypothesis tests, and presented in an interactive Streamlit
dashboard.

**Tech stack:** Python, Pandas, PostgreSQL, SQLAlchemy, SciPy, Matplotlib/Seaborn, Plotly, Streamlit.

## Project structure

```
cart2insights/
├── app/
│   └── app.py                   Streamlit dashboard (6 sections, filters)
├── data/
│   ├── raw/                     the 9 original CSV files go here (not in Git)
│   └── processed/               cleaned tables and features (not in Git)
├── notebooks/
│   ├── 01_data_understanding_and_quality.ipynb   Steps 1-4
│   ├── 02_cleaning_sql_features.ipynb            Steps 5-7
│   ├── 03_eda.ipynb                              Step 8
│   └── 04_statistics_sql_insights.ipynb          Steps 9-11
├── reports/                     generated reports and figures
├── scripts/
│   └── make_sample_data.py      small fake dataset for testing the code
├── sql/
│   ├── schema.sql               PostgreSQL CREATE TABLE statements (keys + indexes)
│   └── business_queries.sql     all business SQL queries
├── src/
│   ├── config.py                paths, file patterns, database URL from .env
│   ├── data_loader.py           Step 3  load CSVs, data dictionary
│   ├── data_quality.py          Step 4  missing, duplicates, types, invalid values, outliers
│   ├── cleaning.py              Step 5  one cleaning function per table
│   ├── db.py                    Step 6  schema from the ER diagram, load, verify
│   ├── features.py              Step 7  order, customer and seller features
│   ├── eda.py                   Step 8  12 charts with computed findings
│   ├── stats_tests.py           Step 9  t-test, ANOVA, chi-square
│   ├── queries.py               Step 10 SQL queries used by the dashboard
│   └── insights.py              Step 11 observation -> interpretation -> impact
├── run_pipeline.py              runs every step in order
├── requirements.txt
├── .env.example                 template for database credentials
└── .gitignore
```

## Setup

1. **Install Python 3.10+ and PostgreSQL 14+.** Make sure the PostgreSQL server is running
   (on macOS: `brew install postgresql@16 && brew services start postgresql@16`, or Postgres.app).
2. **Create a virtual environment and install the libraries:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Add your database credentials:** copy `.env.example` to `.env` and fill in your PostgreSQL
   user and password (default port 5432). The database `cart2insights` is created automatically.
4. **Add the data:** download the dataset and put the 9 CSV files in `data/raw/`.
   Files are matched by keyword (for example any file containing `orders` is the orders
   table), so the standard `olist_*_dataset.csv` names work as they are.

## Run

```bash
python run_pipeline.py          # all steps, about 2-4 minutes on the full dataset
streamlit run app/app.py        # open the dashboard in the browser
```

The pipeline writes these reports to `reports/`:

| File | Contents |
| --- | --- |
| `data_dictionary.md` | every table and column with type, nulls and meaning |
| `data_quality_report.md` | missing values, duplicates, type issues, invalid values, outliers |
| `cleaning_log.md` | rows before and after cleaning |
| `eda_summary.md` + `figures/` | 12 charts, each with a finding |
| `stats_results.md` | the three hypothesis tests in full |
| `business_insights.md` | draft insights and recommendations |

To test the code before downloading the real data:

```bash
python scripts/make_sample_data.py
python run_pipeline.py --raw-dir data/sample
```

The sample numbers are random. Never present results from it.

## Methodology

**Data quality and cleaning.** Duplicates are removed, dates converted, city names
normalised (lower case, no accents), zip codes kept as 5-character text, misspelled
columns renamed, and invalid values fixed or dropped (`not_defined` payments, 0
instalments, delivery before purchase). Only the latest review is kept for each order.
Geolocation is reduced to one row per zip code. Child rows without a parent are dropped
so every foreign key holds. Price outliers are real expensive products and are kept.

**SQL storage.** `src/db.py` defines the schema from the ER diagram with SQLAlchemy.
Tables are created with primary keys, foreign keys and indexes, loaded parents first,
and row counts are verified after loading. Credentials are read from `.env` only.

**Feature engineering.** Items and payments are aggregated to order level before any
join, so revenue is never double counted.

| Feature | Definition |
| --- | --- |
| total_order_value | sum of item prices + freight for the order |
| delivery_days | purchase to customer delivery, in days |
| delivery_delay_days | delivery date minus estimated date (positive = late) |
| delivery_status | On time, Delayed or Not delivered |
| customer_order_count | valid orders per real customer (`customer_unique_id`) |
| total_spend, avg_order_value | per customer |
| seller_revenue, order_count | per seller, valid orders only |
| is_repeat_customer | 1 if the customer has more than one valid order |
| is_valid_sale | 0 for canceled or unavailable orders |

**Statistical tests** (alpha = 0.05), each with assumption checks and a non-parametric
cross-check:

| Question | Test |
| --- | --- |
| Do delayed orders get lower review scores? | Independent two-sample t-test (Welch if variances differ) + Mann-Whitney U |
| Does order value differ across categories? | One-way ANOVA + Kruskal-Wallis, eta squared |
| Is payment method associated with order status? | Chi-square test of independence, Cramer's V |

**SQL analysis.** `src/queries.py` holds 20 queries using WHERE, ORDER BY, GROUP BY,
HAVING, joins, subqueries, CTEs, window functions (RANK, NTILE, LAG, running SUM) and
aggregations. The dashboard runs them with the selected filters as bound parameters.

**Dashboard.** Six sections (business overview, sales, customers, sellers and products,
delivery, customer experience) filtered by purchase month and customer state.

## Key findings

_Fill this in from `reports/business_insights.md` after running on the real data._

1. …
2. …
3. …

## Recommendations

_Fill this in from `reports/business_insights.md`._
