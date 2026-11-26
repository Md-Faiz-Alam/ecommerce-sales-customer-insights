"""Download the raw Olist dataset from Kaggle into data/raw/.

Uses kagglehub. Public datasets usually download without credentials; if Kaggle
asks for auth, create an API token at https://www.kaggle.com/settings and place
kaggle.json in %USERPROFILE%\\.kaggle\\ (never commit it).

Manual fallback: download the zip from
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce and extract the CSVs
into data/raw/.

Usage:
    python scripts/download_data.py           # skip if all files already exist
    python scripts/download_data.py --force   # re-download
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
DATASET = "olistbr/brazilian-ecommerce"
EXPECTED_FILES = [
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]


def missing_files() -> list[str]:
    return [f for f in EXPECTED_FILES if not (RAW_DIR / f).exists()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download even if files exist")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not args.force and not missing_files():
        print(f"All {len(EXPECTED_FILES)} raw files already present in {RAW_DIR}")
        return 0

    import kagglehub

    print(f"Downloading {DATASET} from Kaggle ...")
    src = Path(kagglehub.dataset_download(DATASET, force_download=args.force))
    for name in EXPECTED_FILES:
        matches = list(src.rglob(name))
        if matches:
            shutil.copy2(matches[0], RAW_DIR / name)

    if still_missing := missing_files():
        print(f"Missing after download: {still_missing}", file=sys.stderr)
        return 1
    print(f"Done. Raw files in {RAW_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
