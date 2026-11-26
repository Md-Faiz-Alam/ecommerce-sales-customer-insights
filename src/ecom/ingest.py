"""Read raw Olist CSVs with explicit dtypes (zip prefixes stay strings; leading zeros matter)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ecom.config import RAW_DIR, RAW_FILES

_DTYPES: dict[str, dict[str, str]] = {
    "customers": {"customer_zip_code_prefix": "string"},
    "sellers": {"seller_zip_code_prefix": "string"},
    "geolocation": {"geolocation_zip_code_prefix": "string"},
}


def load_raw(name: str, raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Load one raw table by logical name (see config.RAW_FILES)."""
    path = raw_dir / RAW_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run `.\\tasks.ps1 data` first.")
    return pd.read_csv(path, dtype=_DTYPES.get(name))


def load_all(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    return {name: load_raw(name, raw_dir) for name in RAW_FILES}
