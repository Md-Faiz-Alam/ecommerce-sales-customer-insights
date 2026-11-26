"""Project-wide paths and business constants. No hardcoded drive letters anywhere else."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
WAREHOUSE_PATH = DATA_DIR / "warehouse.duckdb"
REPORTS_DIR = ROOT / "reports"
SQL_DIR = ROOT / "sql"

RAW_FILES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

# Olist volume is negligible before 2017 (329 orders across Sep-Dec 2016) and collapses
# after Aug 2018 (20 orders in Sep-Oct 2018, a data-extraction artefact). Rows are kept
# in staging but flagged; trend, cohort and forecast analyses use only this window.
ANALYSIS_START = pd.Timestamp("2017-01-01")
ANALYSIS_END = pd.Timestamp("2018-09-01")  # exclusive

# Two categories missing from Olist's translation file.
EXTRA_CATEGORY_TRANSLATIONS = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_food_preparers",
}

# Mainland Brazil + islands bounding box; geolocation points outside it are GPS noise.
BRAZIL_LAT = (-34.0, 5.5)
BRAZIL_LNG = (-74.0, -34.0)

CURRENCY = "BRL"
