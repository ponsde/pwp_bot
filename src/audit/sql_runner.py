"""Execute a stored SQL string against the finance DB.

Wraps sqlite3 so the audit layer doesn't have to import it directly, and so
empty / whitespace SQL (which shows up as "无" for pure-RAG task-3 rows)
becomes a safe no-op instead of an exception.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


class SqlRunError(Exception):
    """Raised when a non-empty SQL string fails to execute."""


def run_sql_strict(db_path: Path | str, sql: str) -> list[dict]:
    if not sql or not sql.strip():
        return []
    con = sqlite3.connect(str(db_path))
    try:
        try:
            cur = con.execute(sql)
        except sqlite3.Error as exc:
            raise SqlRunError(str(exc)) from exc
        cols = [d[0] for d in (cur.description or [])]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        con.close()
