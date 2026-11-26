"""End-to-end pipeline: raw CSV -> clean -> validate -> Parquet -> DuckDB -> quality report.

Run:  python -m ecom.pipeline
"""

from __future__ import annotations

import logging
import time

import pandas as pd

from ecom import clean
from ecom.config import REPORTS_DIR
from ecom.ingest import load_all
from ecom.quality import CleaningLog, write_report
from ecom.validate import validate_all
from ecom.warehouse import build_warehouse, write_parquet

log = logging.getLogger("ecom.pipeline")


def clean_all(raw: dict[str, pd.DataFrame], audit: CleaningLog) -> dict[str, pd.DataFrame]:
    return {
        "customers": clean.clean_customers(raw["customers"], audit),
        "sellers": clean.clean_sellers(raw["sellers"], audit),
        "orders": clean.clean_orders(raw["orders"], audit),
        "order_items": clean.clean_order_items(raw["order_items"], audit),
        "payments": clean.clean_payments(raw["payments"], audit),
        "products": clean.clean_products(raw["products"], raw["category_translation"], audit),
        "reviews": clean.clean_reviews(raw["reviews"], audit),
        "geolocation": clean.clean_geolocation(raw["geolocation"], audit),
    }


def run() -> dict[str, pd.DataFrame]:
    t0 = time.perf_counter()
    log.info("Loading raw CSVs")
    raw = load_all()

    log.info("Cleaning")
    audit = CleaningLog()
    tables = clean_all(raw, audit)

    log.info("Validating data contracts")
    validation = validate_all(tables)

    log.info("Writing Parquet + building DuckDB warehouse")
    write_parquet(tables)
    counts = build_warehouse()
    for name, n in counts.items():
        log.info("  %-28s %10s rows", name, f"{n:,}")

    row_counts = {name: (len(raw[name]), len(df)) for name, df in tables.items()}
    report = REPORTS_DIR / "data_quality_report.md"
    write_report(report, audit, row_counts, validation)
    log.info("Data quality report -> %s", report.relative_to(REPORTS_DIR.parent))
    log.info("Done in %.1fs", time.perf_counter() - t0)
    return tables


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    run()


if __name__ == "__main__":
    main()
