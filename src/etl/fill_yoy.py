"""Post-ETL pass: fill NULL *_yoy_growth cells from prev-year base values.

Some PDF-extracted rows have a non-null base metric (revenue, net profit, etc.)
but a NULL yoy_growth because the source report didn't print that column.
When the previous year's same-suffix period is also in the DB with a non-null,
non-zero base value, we can compute the yoy ourselves:

    yoy_pct = round((current - prev) / prev * 100, 4)

The formula matches the units already stored (e.g. 6.678 means 6.678%).
This only fills cells where both current and prev-year base values exist;
it never invents data.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


# (table, yoy_column, base_column). Period-suffix matching works for FY/HY/Q1/Q3.
_YOY_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("income_sheet", "operating_revenue_yoy_growth", "total_operating_revenue"),
    ("income_sheet", "net_profit_yoy_growth", "net_profit"),
    ("core_performance_indicators_sheet", "operating_revenue_yoy_growth", "total_operating_revenue"),
    ("core_performance_indicators_sheet", "net_profit_yoy_growth", "net_profit_10k_yuan"),
    ("core_performance_indicators_sheet", "net_profit_excl_non_recurring_yoy", "net_profit_excl_non_recurring"),
    ("balance_sheet", "asset_total_assets_yoy_growth", "asset_total_assets"),
    ("balance_sheet", "liability_total_liabilities_yoy_growth", "liability_total_liabilities"),
    ("cash_flow_sheet", "net_cash_flow_yoy_growth", "net_cash_flow"),
)


def _fill_one_pair(conn: sqlite3.Connection, table: str, yoy_col: str, base_col: str) -> int:
    """Fill NULL yoy_col rows for a single (table, yoy, base) triple. Returns rows updated."""
    sql = f"""
        UPDATE {table} AS a
        SET {yoy_col} = ROUND(
            (a.{base_col} - (
                SELECT b.{base_col} FROM {table} b
                WHERE b.stock_code = a.stock_code
                  AND b.report_period = (
                    CASE
                      WHEN a.report_period LIKE '%FY' THEN (a.report_year - 1) || 'FY'
                      WHEN a.report_period LIKE '%HY' THEN (a.report_year - 1) || 'HY'
                      WHEN a.report_period LIKE '%Q1' THEN (a.report_year - 1) || 'Q1'
                      WHEN a.report_period LIKE '%Q3' THEN (a.report_year - 1) || 'Q3'
                      ELSE NULL
                    END
                  )
            )) * 1.0 / (
                SELECT b.{base_col} FROM {table} b
                WHERE b.stock_code = a.stock_code
                  AND b.report_period = (
                    CASE
                      WHEN a.report_period LIKE '%FY' THEN (a.report_year - 1) || 'FY'
                      WHEN a.report_period LIKE '%HY' THEN (a.report_year - 1) || 'HY'
                      WHEN a.report_period LIKE '%Q1' THEN (a.report_year - 1) || 'Q1'
                      WHEN a.report_period LIKE '%Q3' THEN (a.report_year - 1) || 'Q3'
                      ELSE NULL
                    END
                  )
            ) * 100, 4
        )
        WHERE a.{yoy_col} IS NULL
          AND a.{base_col} IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM {table} b
            WHERE b.stock_code = a.stock_code
              AND b.report_period = (
                CASE
                  WHEN a.report_period LIKE '%FY' THEN (a.report_year - 1) || 'FY'
                  WHEN a.report_period LIKE '%HY' THEN (a.report_year - 1) || 'HY'
                  WHEN a.report_period LIKE '%Q1' THEN (a.report_year - 1) || 'Q1'
                  WHEN a.report_period LIKE '%Q3' THEN (a.report_year - 1) || 'Q3'
                  ELSE NULL
                END
              )
              AND b.{base_col} IS NOT NULL
              AND b.{base_col} != 0
          )
    """
    cursor = conn.execute(sql)
    return cursor.rowcount or 0


def fill_missing_yoy(db_path: Path | str, pairs: Iterable[tuple[str, str, str]] = _YOY_PAIRS) -> dict[str, int]:
    """Run the fill across all configured (table, yoy, base) pairs.

    Returns a dict keyed "{table}.{yoy_col}" -> rows updated.
    """
    summary: dict[str, int] = {}
    with sqlite3.connect(str(db_path)) as conn:
        for table, yoy_col, base_col in pairs:
            try:
                updated = _fill_one_pair(conn, table, yoy_col, base_col)
            except sqlite3.OperationalError as exc:
                logger.warning("fill_missing_yoy skipped %s.%s: %s", table, yoy_col, exc)
                continue
            summary[f"{table}.{yoy_col}"] = updated
            if updated:
                logger.info("fill_missing_yoy: %s.%s filled %d row(s)", table, yoy_col, updated)
        conn.commit()
    return summary
