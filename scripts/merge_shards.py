"""Merge ETL shard DBs into finance.db. Standalone version (no ATTACH)."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.etl.loader import ETLLoader


TABLES = (
    "core_performance_indicators_sheet",
    "balance_sheet",
    "income_sheet",
    "cash_flow_sheet",
    "_share_capital_cache",
)


def _copy_table(src_conn: sqlite3.Connection, dst_conn: sqlite3.Connection, table: str) -> int:
    try:
        cursor = src_conn.execute(f'SELECT * FROM "{table}"')
    except sqlite3.OperationalError as exc:
        print(f"  SKIP {table} (src): {exc}", flush=True)
        return 0
    cols = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    if not rows:
        return 0
    placeholders = ",".join(["?"] * len(cols))
    column_list = ",".join(f'"{c}"' for c in cols)
    sql = f'INSERT OR REPLACE INTO "{table}" ({column_list}) VALUES ({placeholders})'
    try:
        dst_conn.executemany(sql, rows)
    except sqlite3.OperationalError as exc:
        print(f"  SKIP {table} (dst): {exc}", flush=True)
        return 0
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-dir", default="data/db/shards")
    parser.add_argument("--output", default="data/db/finance.db")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    target = Path(args.output).resolve()
    shard_dir = Path(args.shard_dir).resolve()
    if target.exists():
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Initialize schema
    ETLLoader(target)

    dst = sqlite3.connect(target)
    dst.execute("PRAGMA journal_mode=WAL")
    # Eagerly create cache table (usually lazy-created in loader.py)
    dst.execute(
        """
        CREATE TABLE IF NOT EXISTS _share_capital_cache (
            stock_code TEXT NOT NULL,
            report_period TEXT NOT NULL,
            share_capital REAL,
            PRIMARY KEY (stock_code, report_period)
        )
        """
    )
    totals = {t: 0 for t in TABLES}
    for i in range(args.workers):
        src_path = shard_dir / f"finance_shard_{i}.db"
        if not src_path.exists():
            print(f"shard_{i}: missing ({src_path})", flush=True)
            continue
        src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
        print(f"shard_{i}: merging from {src_path}")
        for t in TABLES:
            n = _copy_table(src, dst, t)
            totals[t] += n
            print(f"  {t}: +{n}")
        src.close()
    dst.commit()

    print("=== merged totals ===")
    for t in TABLES:
        try:
            cnt = dst.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except sqlite3.OperationalError:
            cnt = 0
        print(f"{t}: {cnt}")
    dst.close()


if __name__ == "__main__":
    main()
