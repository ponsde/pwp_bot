"""Data-quality audit for finance.db.

Six dimensions, each a pure function on sqlite3.Connection so they're testable
in isolation. The CLI entry at the bottom composes them and emits JSON + a
short console summary.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


TABLES: list[str] = [
    "core_performance_indicators_sheet",
    "balance_sheet",
    "income_sheet",
    "cash_flow_sheet",
]

KEY_FIELDS: dict[str, list[str]] = {
    "core_performance_indicators_sheet": [
        "total_operating_revenue",
        "net_profit_10k_yuan",
        "roe",
        "eps",
        "net_asset_per_share",
    ],
    "balance_sheet": [
        "asset_total_assets",
        "liability_total_liabilities",
        "equity_total_equity",
        "asset_cash_and_cash_equivalents",
    ],
    "income_sheet": [
        "total_operating_revenue",
        "operating_profit",
        "total_profit",
        "net_profit",
    ],
    "cash_flow_sheet": [
        "net_cash_flow",
        "operating_cf_net_amount",
        "investing_cf_net_amount",
        "financing_cf_net_amount",
    ],
}


def audit_coverage(conn: sqlite3.Connection) -> dict:
    out: dict = {}
    for tbl in TABLES:
        row = conn.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT stock_code), COUNT(DISTINCT report_period) FROM {tbl}"
        ).fetchone()
        out[tbl] = {"rows": row[0], "companies": row[1], "periods": row[2]}
    return out


def audit_null_rates(conn: sqlite3.Connection) -> dict:
    out: dict = {}
    for tbl, fields in KEY_FIELDS.items():
        total = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        if total == 0:
            out[tbl] = {f: None for f in fields}
            continue
        per_field: dict[str, float] = {}
        for field in fields:
            n_null = conn.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {field} IS NULL").fetchone()[0]
            per_field[field] = round(n_null / total, 4)
        out[tbl] = per_field
    return out


def audit_balance_equation(conn: sqlite3.Connection, rel_tolerance: float = 0.01) -> list[dict]:
    rows = conn.execute(
        """
        SELECT stock_code, stock_abbr, report_period,
               asset_total_assets, liability_total_liabilities, equity_total_equity
        FROM balance_sheet
        WHERE asset_total_assets IS NOT NULL
          AND liability_total_liabilities IS NOT NULL
          AND equity_total_equity IS NOT NULL
        """
    ).fetchall()
    result: list[dict] = []
    for code, abbr, period, assets, liab, equity in rows:
        diff = assets - (liab + equity)
        denom = max(abs(assets), abs(liab + equity), 1.0)
        rel = abs(diff) / denom
        if rel > rel_tolerance:
            result.append({
                "stock_code": code,
                "stock_abbr": abbr,
                "report_period": period,
                "assets": assets,
                "liab_plus_equity": liab + equity,
                "diff": round(diff, 2),
                "rel_error": round(rel, 4),
            })
    return result


def audit_cross_table_consistency(conn: sqlite3.Connection, rel_tolerance: float = 0.05) -> list[dict]:
    """Compare income.net_profit vs core.net_profit_10k_yuan.

    Both are stored in 万元 (extractor convention; despite the income column
    name suggesting absolute yuan, inspection shows the stored value is in
    10k yuan — matches the validator's direct comparison in validator.py).
    """
    rows = conn.execute(
        """
        SELECT i.stock_code, i.stock_abbr, i.report_period,
               i.net_profit, c.net_profit_10k_yuan
        FROM income_sheet i
        JOIN core_performance_indicators_sheet c
          ON i.stock_code = c.stock_code AND i.report_period = c.report_period
        WHERE i.net_profit IS NOT NULL AND c.net_profit_10k_yuan IS NOT NULL
        """
    ).fetchall()
    result: list[dict] = []
    for code, abbr, period, income_np, core_np in rows:
        denom = max(abs(income_np), abs(core_np), 1.0)
        rel = abs(income_np - core_np) / denom
        if rel > rel_tolerance:
            result.append({
                "stock_code": code,
                "stock_abbr": abbr,
                "report_period": period,
                "income_net_profit": income_np,
                "core_net_profit": core_np,
                "rel_error": round(rel, 4),
            })
    return result


def audit_missing_periods(
    conn: sqlite3.Connection,
    expected: list[tuple[str, str]],
) -> list[dict]:
    present = {
        (row[0], row[1])
        for row in conn.execute(
            "SELECT DISTINCT stock_code, report_period FROM core_performance_indicators_sheet"
        ).fetchall()
    }
    missing = [{"stock_code": c, "report_period": p} for c, p in expected if (c, p) not in present]
    return missing


def audit_yoy_outliers(
    conn: sqlite3.Connection,
    revenue_threshold: float = 500.0,
    profit_threshold: float = 1000.0,
) -> list[dict]:
    out: list[dict] = []
    for tbl, revenue_col, profit_col in [
        ("core_performance_indicators_sheet", "operating_revenue_yoy_growth", "net_profit_yoy_growth"),
        ("income_sheet", "operating_revenue_yoy_growth", "net_profit_yoy_growth"),
    ]:
        rows = conn.execute(
            f"""
            SELECT stock_code, stock_abbr, report_period, {revenue_col}, {profit_col}
            FROM {tbl}
            WHERE (ABS(COALESCE({revenue_col}, 0)) > ? OR ABS(COALESCE({profit_col}, 0)) > ?)
            """,
            [revenue_threshold, profit_threshold],
        ).fetchall()
        for code, abbr, period, rev_yoy, profit_yoy in rows:
            out.append({
                "table": tbl,
                "stock_code": code,
                "stock_abbr": abbr,
                "report_period": period,
                "revenue_yoy": rev_yoy,
                "profit_yoy": profit_yoy,
            })
    return out


def _build_expected_periods(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    codes = [r[0] for r in conn.execute(
        "SELECT DISTINCT stock_code FROM core_performance_indicators_sheet"
    ).fetchall()]
    periods = [r[0] for r in conn.execute(
        "SELECT DISTINCT report_period FROM core_performance_indicators_sheet"
    ).fetchall()]
    return [(c, p) for c in codes for p in periods]


def run_audit(
    conn: sqlite3.Connection,
    expected_periods: list[tuple[str, str]] | None,
) -> dict:
    if expected_periods is None:
        expected_periods = _build_expected_periods(conn)
    return {
        "coverage": audit_coverage(conn),
        "null_rates": audit_null_rates(conn),
        "balance_equation": audit_balance_equation(conn),
        "cross_table_consistency": audit_cross_table_consistency(conn),
        "missing_periods": audit_missing_periods(conn, expected_periods),
        "yoy_outliers": audit_yoy_outliers(conn),
    }


def _print_summary(report: dict) -> None:
    print("=== finance.db audit ===")
    cov = report["coverage"]
    core = cov["core_performance_indicators_sheet"]
    print(f"coverage: rows={core['rows']} companies={core['companies']} periods={core['periods']}")
    print("  row counts: " + " ".join(f"{k.split('_')[0]}={v['rows']}" for k, v in cov.items()))
    print("null_rates (worst per table):")
    for tbl, fields in report["null_rates"].items():
        worst = max(fields.items(), key=lambda kv: kv[1] or 0)
        print(f"  {tbl:40s} {worst[0]}={(worst[1] or 0)*100:.1f}%")
    print(f"balance_mismatch     : {len(report['balance_equation'])} rows")
    print(f"cross_inconsistency  : {len(report['cross_table_consistency'])} rows")
    print(f"missing_periods      : {len(report['missing_periods'])} cells")
    print(f"yoy_outliers         : {len(report['yoy_outliers'])} rows")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/db/finance.db")
    parser.add_argument("--out", default="logs/audit_db.json")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        raise SystemExit(f"db not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        report = run_audit(conn, expected_periods=None)
    finally:
        conn.close()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    _print_summary(report)
    print(f"full report: {out_path}")


if __name__ == "__main__":
    main()
