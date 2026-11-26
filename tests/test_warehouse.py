"""Tests for the SQL test runner (in-memory DuckDB, no real data needed)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from ecom.warehouse import SqlTestError, run_sql_tests


def _sql_dir(tmp_path: Path, tests: dict[str, str]) -> Path:
    (tmp_path / "tests").mkdir()
    for name, sql in tests.items():
        (tmp_path / "tests" / f"{name}.sql").write_text(sql, encoding="utf-8")
    return tmp_path


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute("CREATE TABLE t AS SELECT * FROM (VALUES (1), (2), (2)) v(id)")
    yield c
    c.close()


def test_passing_sql_test_returns_passed(con, tmp_path):
    sql_dir = _sql_dir(tmp_path, {"test_ok": "SELECT id FROM t WHERE id > 10"})
    assert run_sql_tests(con, sql_dir) == {"sql:test_ok": "passed"}


def test_failing_sql_test_raises(con, tmp_path):
    sql_dir = _sql_dir(
        tmp_path, {"test_unique": "SELECT id, count(*) FROM t GROUP BY id HAVING count(*) > 1"}
    )
    with pytest.raises(SqlTestError, match="test_unique"):
        run_sql_tests(con, sql_dir)


def test_project_sql_tests_all_exist():
    """Guard: the project ships its SQL data tests."""
    tests = list((Path(__file__).parents[1] / "sql" / "tests").glob("test_*.sql"))
    assert len(tests) >= 8
