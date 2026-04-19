"""Execute a stored SQL string against the finance DB.

Wraps sqlite3 so the audit layer doesn't have to import it directly, and so
empty / whitespace SQL (which shows up as "无" for pure-RAG task-3 rows)
becomes a safe no-op instead of an exception.

xlsx cells often pack multiple SQL statements (separated by ``;`` or blank
lines) because the assistant explored schema before issuing the final query,
or because a multi-turn conversation ran several queries. ``run_sql_strict``
runs every statement and returns the UNION of every row set — downstream
checks need all of them to verify numbers the content text cites.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path


class SqlRunError(Exception):
    """Raised when every statement in the SQL blob fails to execute."""


_SPLIT = re.compile(r";\s*(?:\r?\n)+|(?:\r?\n){2,}")


def _split_statements(sql: str) -> list[str]:
    parts = [p.strip().rstrip(";").strip() for p in _SPLIT.split(sql)]
    return [p for p in parts if p]


def run_sql_strict(db_path: Path | str, sql: str) -> list[dict]:
    if not sql or not sql.strip():
        return []
    statements = _split_statements(sql)
    if not statements:
        return []
    con = sqlite3.connect(str(db_path))
    all_rows: list[dict] = []
    any_ok = False
    last_err: str | None = None
    try:
        for stmt in statements:
            try:
                cur = con.execute(stmt)
            except sqlite3.Error as exc:
                last_err = str(exc)
                continue
            any_ok = True
            cols = [d[0] for d in (cur.description or [])]
            for row in cur.fetchall():
                all_rows.append(dict(zip(cols, row)))
        if not any_ok and last_err is not None:
            raise SqlRunError(last_err)
        return all_rows
    finally:
        con.close()
