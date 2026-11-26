"""Persist clean tables to Parquet and load them into a local DuckDB warehouse.

DuckDB runs in-process (no server, no LOAD DATA INFILE paths), so anyone who clones the
repo can rebuild the warehouse with one command. Clean tables land in the `staging`
schema; SQL models in sql/ build the analytics marts on top of them.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from ecom.config import PROCESSED_DIR, SQL_DIR, WAREHOUSE_PATH


def write_parquet(tables: dict[str, pd.DataFrame], out_dir: Path = PROCESSED_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_parquet(out_dir / f"{name}.parquet", index=False)


def build_warehouse(
    processed_dir: Path = PROCESSED_DIR,
    db_path: Path = WAREHOUSE_PATH,
    sql_dir: Path = SQL_DIR,
) -> dict[str, int]:
    """(Re)create staging tables from Parquet, then run any SQL models in sql/ in order."""
    db_path.unlink(missing_ok=True)
    counts: dict[str, int] = {}
    with duckdb.connect(str(db_path)) as con:
        con.execute("CREATE SCHEMA staging")
        for pq in sorted(processed_dir.glob("*.parquet")):
            con.execute(
                f"CREATE TABLE staging.{pq.stem} AS SELECT * FROM read_parquet(?)", [str(pq)]
            )
            counts[f"staging.{pq.stem}"] = con.execute(
                f"SELECT count(*) FROM staging.{pq.stem}"
            ).fetchone()[0]

        # SQL models: sql/<NN_layer>/<NN_model>.sql, executed in lexical order.
        for script in sorted(sql_dir.glob("[0-9][0-9]_*/*.sql")):
            con.execute(script.read_text(encoding="utf-8"))
    return counts
