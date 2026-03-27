from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable

from src.etl.schema import load_schema_metadata


RANGE_RULES = {
    "core_performance_indicators_sheet": {
        "eps": (-50, 50),
        "total_operating_revenue": (0, None),
        "net_profit_10k_yuan": (-1_000_000_000, 1_000_000_000),
        "roe": (-500, 500),
        "roe_weighted_excl_non_recurring": (-500, 500),
    },
    "income_sheet": {
        "total_operating_revenue": (0, None),
        "net_profit": (-1_000_000_000, 1_000_000_000),
        "total_profit": (-1_000_000_000, 1_000_000_000),
    },
    "cash_flow_sheet": {
        "net_cash_flow": (-1_000_000_000, 1_000_000_000),
        "operating_cf_net_amount": (-1_000_000_000, 1_000_000_000),
    },
    "balance_sheet": {
        "asset_total_assets": (0, None),
        "liability_total_liabilities": (0, None),
        "equity_total_equity": (-1_000_000_000, 1_000_000_000),
    },
}

YOY_FIELD_MAP = {
    "core_performance_indicators_sheet": [
        ("total_operating_revenue", "operating_revenue_yoy_growth"),
        ("net_profit_10k_yuan", "net_profit_yoy_growth"),
        ("net_profit_excl_non_recurring", "net_profit_excl_non_recurring_yoy"),
    ],
    "income_sheet": [
        ("total_operating_revenue", "operating_revenue_yoy_growth"),
        ("net_profit", "net_profit_yoy_growth"),
    ],
    "cash_flow_sheet": [
        ("net_cash_flow", "net_cash_flow_yoy_growth"),
    ],
    "balance_sheet": [
        ("asset_total_assets", "asset_total_assets_yoy_growth"),
        ("liability_total_liabilities", "liability_total_liabilities_yoy_growth"),
    ],
}

_PERIOD_ORDER = {"Q1": 1, "HY": 2, "Q3": 3, "FY": 4}


def previous_yoy_period(report_period: str) -> str | None:
    year = int(report_period[:4])
    suffix = report_period[4:]
    if suffix in _PERIOD_ORDER:
        return f"{year - 1}{suffix}"
    return None


def compute_growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / abs(previous) * 100, 4)


def check_ranges(conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    for table, fields in RANGE_RULES.items():
        for field, (min_value, max_value) in fields.items():
            violation_clauses: list[str] = []
            params: list[float] = []
            if min_value is not None:
                violation_clauses.append(f"{field} < ?")
                params.append(min_value)
            if max_value is not None:
                violation_clauses.append(f"{field} > ?")
                params.append(max_value)
            if not violation_clauses:
                continue
            sql = (
                f"SELECT stock_code, report_period, {field} FROM {table} "
                f"WHERE {field} IS NOT NULL AND ({' OR '.join(violation_clauses)})"
            )
            for stock_code, report_period, value in conn.execute(sql, params):
                issues.append(f"[range] {table}.{field} {stock_code} {report_period} = {value}")
    return issues


def check_cross_table_consistency(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT c.stock_code, c.report_period, c.total_operating_revenue, i.total_operating_revenue
        FROM core_performance_indicators_sheet c
        JOIN income_sheet i
          ON c.stock_code = i.stock_code AND c.report_period = i.report_period
        WHERE c.total_operating_revenue IS NOT NULL
          AND i.total_operating_revenue IS NOT NULL
          AND ABS(c.total_operating_revenue - i.total_operating_revenue) > 0.01
        """
    ).fetchall()
    return [
        f"[cross-table] revenue mismatch {stock_code} {report_period}: core={core_value}, income={income_value}"
        for stock_code, report_period, core_value, income_value in rows
    ]


def check_yoy_validation(conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    for table, mappings in YOY_FIELD_MAP.items():
        rows = conn.execute(
            f"SELECT stock_code, report_period, * FROM {table}"
        )
        col_names = [desc[0] for desc in rows.description]
        data = {}
        for row in rows.fetchall():
            record = dict(zip(col_names, row))
            data[(record["stock_code"], record["report_period"])] = record
        for (stock_code, report_period), record in data.items():
            prev_period = previous_yoy_period(report_period)
            prev = data.get((stock_code, prev_period))
            for value_field, yoy_field in mappings:
                manual = compute_growth(record.get(value_field), None if prev is None else prev.get(value_field))
                actual = record.get(yoy_field)
                if manual is None and actual is None:
                    continue
                if manual is None or actual is None or abs(manual - actual) > 0.01:
                    issues.append(
                        f"[yoy] {table}.{yoy_field} {stock_code} {report_period}: db={actual}, manual={manual}"
                    )
    return issues


def coverage_report(conn: sqlite3.Connection) -> list[str]:
    lines: list[str] = []
    metadata = load_schema_metadata()
    for table, fields in metadata.items():
        tracked = [field.name for field in fields if field.name not in {"serial_number", "stock_code", "stock_abbr", "report_period", "report_year"}]
        total_rows = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        lines.append(f"[coverage] {table} rows={total_rows}")
        if total_rows == 0:
            continue
        actual_columns = {
            row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        }
        for field in tracked:
            if field not in actual_columns:
                continue
            non_null = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {field} IS NOT NULL").fetchone()[0]
            ratio = round(non_null / total_rows * 100, 2)
            lines.append(f"  - {field}: {non_null}/{total_rows} ({ratio}%)")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="ETL quality checks for financial statement DB")
    parser.add_argument("db_path", type=Path)
    args = parser.parse_args()

    with sqlite3.connect(args.db_path) as conn:
        issues = []
        issues.extend(check_ranges(conn))
        issues.extend(check_cross_table_consistency(conn))
        issues.extend(check_yoy_validation(conn))
        coverage = coverage_report(conn)

    print("# ETL Quality Check Report")
    print("\n## Issues")
    if issues:
        for issue in issues:
            print(issue)
    else:
        print("No issues found.")

    print("\n## Coverage")
    for line in coverage:
        print(line)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
