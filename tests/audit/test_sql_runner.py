import sqlite3
from pathlib import Path

import pytest

from src.audit.sql_runner import run_sql_strict, SqlRunError


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "t.db"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE x (a INTEGER, b TEXT)")
    con.execute("INSERT INTO x VALUES (1, 'foo')")
    con.execute("INSERT INTO x VALUES (2, 'bar')")
    con.commit()
    con.close()
    return db_path


def test_run_sql_returns_dicts(tmp_db: Path):
    rows = run_sql_strict(tmp_db, "SELECT a, b FROM x ORDER BY a")
    assert rows == [{"a": 1, "b": "foo"}, {"a": 2, "b": "bar"}]


def test_run_sql_raises_on_bad_sql(tmp_db: Path):
    with pytest.raises(SqlRunError):
        run_sql_strict(tmp_db, "SELECT * FROM does_not_exist")


def test_run_sql_empty_result_ok(tmp_db: Path):
    assert run_sql_strict(tmp_db, "SELECT a FROM x WHERE a = 99") == []


def test_run_sql_handles_none_or_empty_input(tmp_db: Path):
    assert run_sql_strict(tmp_db, "") == []
    assert run_sql_strict(tmp_db, "   ") == []
