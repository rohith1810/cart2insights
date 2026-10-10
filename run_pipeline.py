"""Run the full Cart2Insights pipeline, from raw CSVs to insights.

    python run_pipeline.py                      # uses data/raw and the database in .env
    python run_pipeline.py --raw-dir data/sample --skip-eda

Steps: load -> quality report -> clean -> SQL -> features -> EDA -> statistics -> insights.
"""
import argparse
import logging
import time
from pathlib import Path

from src.cleaning import clean_all
from src.config import FIGURES_DIR, PROCESSED_DIR, RAW_DIR, REPORTS_DIR, SQL_DIR
from src.data_loader import build_data_dictionary, describe_tables, load_raw_tables
from src.data_quality import run_quality_report
from src.db import (FEATURE_TABLES, RAW_TABLES, export_postgres_schema, get_engine, load_tables,
                    reset_schema, verify_counts)
from src.eda import load_order_features, run_eda
from src.features import build_all_features
from src.insights import write_insights
from src.queries import export_queries
from src.stats_tests import run_all_tests

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("pipeline")


def write_markdown(path: Path, title: str, sections: dict) -> None:
    lines = [f"# {title}", ""]
    for heading, df in sections.items():
        lines += [f"## {heading}", "",
                  df.to_markdown(index=False) if len(df) else "_No issues found._", ""]
    path.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR, help="folder with the 9 CSV files")
    parser.add_argument("--skip-eda", action="store_true", help="skip charts (faster)")
    args = parser.parse_args()
    start = time.time()
    for folder in (PROCESSED_DIR, REPORTS_DIR, FIGURES_DIR, SQL_DIR):
        folder.mkdir(parents=True, exist_ok=True)

    log.info("Step 3  Loading raw data from %s", args.raw_dir)
    raw = load_raw_tables(args.raw_dir)
    write_markdown(REPORTS_DIR / "data_dictionary.md", "Data dictionary", {
        "Tables": describe_tables(raw), "Columns": build_data_dictionary(raw)})

    log.info("Step 4  Data quality analysis")
    write_markdown(REPORTS_DIR / "data_quality_report.md", "Data quality report (raw data)",
                   run_quality_report(raw))

    log.info("Step 5  Cleaning")
    clean, clean_log = clean_all(raw)
    for name, df in clean.items():
        df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False)
    write_markdown(REPORTS_DIR / "cleaning_log.md", "Cleaning log", {"Rows before and after": clean_log})
    log.info("\n%s", clean_log.to_string(index=False))

    log.info("Step 6  Loading clean data into SQL")
    engine = get_engine()
    reset_schema(engine)
    load_tables(engine, clean, RAW_TABLES)
    export_postgres_schema()

    log.info("Step 7  Feature engineering")
    features = build_all_features(clean)
    load_tables(engine, features, FEATURE_TABLES)
    for name, df in features.items():
        df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False)
    counts = verify_counts(engine, {**clean, **features})
    log.info("Row-count check\n%s", counts.to_string(index=False))
    if not counts["match"].all():
        raise RuntimeError("Row counts in the database do not match the loaded data.")

    of = load_order_features(engine)
    if not args.skip_eda:
        log.info("Step 8  EDA")
        run_eda(engine)

    log.info("Step 9  Statistical tests")
    results = run_all_tests(of)
    for r in results:
        log.info("%s -> %s (p %s)", r["name"], r["decision"], r["results"]["p-value"])

    log.info("Step 10 Exporting SQL queries")
    export_queries()

    log.info("Step 11 Business insights")
    write_insights(engine, results)

    log.info("Done in %.1f s. Reports are in %s", time.time() - start, REPORTS_DIR)
    log.info("Start the dashboard with:  streamlit run app/app.py")


if __name__ == "__main__":
    main()
