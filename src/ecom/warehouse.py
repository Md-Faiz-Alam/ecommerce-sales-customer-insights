"""Persist clean tables to Parquet, load them into DuckDB, build SQL models, run SQL tests.

DuckDB runs in-process (no server, no LOAD DATA INFILE paths), so anyone who clones the
repo can rebuild the warehouse with one command.

Layers:
    staging.*   clean tables from Python (this module)
    marts.*     star schema           sql/01_marts/*.sql
    analysis.*  business views        sql/02_analysis/*.sql
    sql/tests/  data tests: each query returns the rows that violate a rule (0 rows = pass)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from ecom.config import PROCESSED_DIR, SQL_DIR, WAREHOUSE_PATH


class SqlTestError(Exception):
    pass


@dataclass
class BuildResult:
    row_counts: dict[str, int]
    tests: dict[str, str]


def write_parquet(tables: dict[str, pd.DataFrame], out_dir: Path = PROCESSED_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_parquet(out_dir / f"{name}.parquet", index=False)


def _load_staging(con: duckdb.DuckDBPyConnection, processed_dir: Path) -> None:
    con.execute("CREATE SCHEMA staging")
    for pq in sorted(processed_dir.glob("*.parquet")):
        con.execute(f"CREATE TABLE staging.{pq.stem} AS SELECT * FROM read_parquet(?)", [str(pq)])


def _run_models(con: duckdb.DuckDBPyConnection, sql_dir: Path) -> None:
    """Execute sql/<NN_layer>/<NN_model>.sql in lexical order (layers, then models)."""
    for script in sorted(sql_dir.glob("[0-9][0-9]_*/*.sql")):
        try:
            con.execute(script.read_text(encoding="utf-8"))
        except duckdb.Error as exc:
            raise RuntimeError(f"SQL model failed: {script.relative_to(sql_dir)}\n{exc}") from exc


def run_sql_tests(con: duckdb.DuckDBPyConnection, sql_dir: Path = SQL_DIR) -> dict[str, str]:
    """Run every sql/tests/*.sql. A test passes when it returns zero rows."""
    results: dict[str, str] = {}
    failures: list[str] = []
    for script in sorted((sql_dir / "tests").glob("*.sql")):
        bad = con.execute(script.read_text(encoding="utf-8")).fetchall()
        name = f"sql:{script.stem}"
        if bad:
            results[name] = f"FAILED ({len(bad)} rows, e.g. {bad[0]})"
            failures.append(f"{script.name}: {len(bad)} violating rows, first = {bad[0]}")
        else:
            results[name] = "passed"
    if failures:
        raise SqlTestError("SQL data tests failed:\n  " + "\n  ".join(failures))
    return results


def _row_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    tables = con.execute(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_schema IN ('staging', 'marts') AND table_type = 'BASE TABLE' "
        "ORDER BY 1, 2"
    ).fetchall()
    return {
        f"{s}.{t}": con.execute(f"SELECT count(*) FROM {s}.{t}").fetchone()[0] for s, t in tables
    }


def build_warehouse(
    processed_dir: Path = PROCESSED_DIR,
    db_path: Path = WAREHOUSE_PATH,
    sql_dir: Path = SQL_DIR,
) -> BuildResult:
    """Rebuild the warehouse from scratch: staging -> marts -> analysis -> tests."""
    db_path.unlink(missing_ok=True)
    with duckdb.connect(str(db_path)) as con:
        _load_staging(con, processed_dir)
        _run_models(con, sql_dir)
        tests = run_sql_tests(con, sql_dir)
        return BuildResult(row_counts=_row_counts(con), tests=tests)
