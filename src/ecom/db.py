"""Read-only access to the DuckDB warehouse for notebooks and the app."""

from __future__ import annotations

from functools import cache

import duckdb
import pandas as pd

from ecom.config import WAREHOUSE_PATH


@cache
def _connection() -> duckdb.DuckDBPyConnection:
    if not WAREHOUSE_PATH.exists():
        raise FileNotFoundError(f"{WAREHOUSE_PATH} not found. Run `.\\tasks.ps1 pipeline` first.")
    return duckdb.connect(str(WAREHOUSE_PATH), read_only=True)


def query(sql: str, params: list | None = None) -> pd.DataFrame:
    """Run SQL against the warehouse and return a DataFrame."""
    return _connection().execute(sql, params or []).df()


def table(name: str) -> pd.DataFrame:
    """Fetch a whole table or view, e.g. table('analysis.kpi_monthly')."""
    return query(f"SELECT * FROM {name}")
