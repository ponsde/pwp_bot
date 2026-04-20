"""Tests for audit_db — use in-memory sqlite with hand-crafted rows."""
import sqlite3

import pytest

from scripts import audit_db


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.executescript(
        """
        CREATE TABLE core_performance_indicators_sheet (
            stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER,
            total_operating_revenue REAL, net_profit_10k_yuan REAL, roe REAL,
            eps REAL, net_asset_per_share REAL,
            operating_revenue_yoy_growth REAL, net_profit_yoy_growth REAL,
            net_profit_excl_non_recurring REAL, net_profit_excl_non_recurring_yoy REAL,
            PRIMARY KEY(stock_code, report_period)
        );
        CREATE TABLE balance_sheet (
            stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER,
            asset_total_assets REAL, liability_total_liabilities REAL, equity_total_equity REAL,
            asset_cash_and_cash_equivalents REAL,
            asset_total_assets_yoy_growth REAL, liability_total_liabilities_yoy_growth REAL,
            PRIMARY KEY(stock_code, report_period)
        );
        CREATE TABLE income_sheet (
            stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER,
            total_operating_revenue REAL, operating_profit REAL, total_profit REAL,
            net_profit REAL,
            operating_revenue_yoy_growth REAL, net_profit_yoy_growth REAL,
            PRIMARY KEY(stock_code, report_period)
        );
        CREATE TABLE cash_flow_sheet (
            stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER,
            net_cash_flow REAL, operating_cf_net_amount REAL,
            investing_cf_net_amount REAL, financing_cf_net_amount REAL,
            net_cash_flow_yoy_growth REAL,
            PRIMARY KEY(stock_code, report_period)
        );
        """
    )
    c.executemany(
        "INSERT INTO core_performance_indicators_sheet (stock_code, stock_abbr, report_period, report_year, total_operating_revenue, net_profit_10k_yuan, roe, eps, net_asset_per_share) VALUES (?,?,?,?,?,?,?,?,?)",
        [
            ("000001", "甲", "2024FY", 2024, 10000.0, 1000.0, 10.0, 0.5, 5.0),
            ("000001", "甲", "2023FY", 2023, 8000.0, 800.0, None, 0.4, 4.0),
            ("000002", "乙", "2024FY", 2024, 20000.0, 2000.0, 12.0, 1.0, 10.0),
            ("000002", "乙", "2023FY", 2023, 18000.0, 1500.0, 11.0, 0.9, 9.0),
        ],
    )
    c.executemany(
        "INSERT INTO balance_sheet (stock_code, stock_abbr, report_period, report_year, asset_total_assets, liability_total_liabilities, equity_total_equity, asset_cash_and_cash_equivalents) VALUES (?,?,?,?,?,?,?,?)",
        [
            ("000001", "甲", "2024FY", 2024, 1000.0, 400.0, 600.0, 200.0),
            ("000001", "甲", "2023FY", 2023, 900.0, 400.0, 600.0, 180.0),
            ("000002", "乙", "2024FY", 2024, 2000.0, 800.0, 1200.0, 400.0),
            ("000002", "乙", "2023FY", 2023, 1800.0, 700.0, 1100.0, 360.0),
        ],
    )
    c.executemany(
        "INSERT INTO income_sheet (stock_code, stock_abbr, report_period, report_year, total_operating_revenue, operating_profit, total_profit, net_profit) VALUES (?,?,?,?,?,?,?,?)",
        [
            ("000001", "甲", "2024FY", 2024, 10000.0, 1500.0, 1400.0, 1000.0),
            ("000001", "甲", "2023FY", 2023, 8000.0, 1200.0, 1100.0, 800.0),
            ("000002", "乙", "2024FY", 2024, 20000.0, 3000.0, 2800.0, 999999.0),
            ("000002", "乙", "2023FY", 2023, 18000.0, 2200.0, 2000.0, 1500.0),
        ],
    )
    c.executemany(
        "INSERT INTO cash_flow_sheet (stock_code, stock_abbr, report_period, report_year, net_cash_flow, operating_cf_net_amount, investing_cf_net_amount, financing_cf_net_amount) VALUES (?,?,?,?,?,?,?,?)",
        [
            ("000001", "甲", "2024FY", 2024, 100.0, 200.0, -50.0, -50.0),
            ("000001", "甲", "2023FY", 2023, 90.0, 180.0, -40.0, -50.0),
            ("000002", "乙", "2024FY", 2024, 300.0, 500.0, -100.0, -100.0),
            ("000002", "乙", "2023FY", 2023, 250.0, 450.0, -100.0, -100.0),
        ],
    )
    c.commit()
    return c


def test_audit_coverage_counts_rows_companies_periods(conn):
    result = audit_db.audit_coverage(conn)
    assert result["core_performance_indicators_sheet"]["rows"] == 4
    assert result["core_performance_indicators_sheet"]["companies"] == 2
    assert result["core_performance_indicators_sheet"]["periods"] == 2


def test_audit_null_rates_detects_null_roe(conn):
    result = audit_db.audit_null_rates(conn)
    assert result["core_performance_indicators_sheet"]["roe"] == pytest.approx(0.25)
    assert result["core_performance_indicators_sheet"]["total_operating_revenue"] == 0.0


def test_audit_balance_equation_finds_mismatch(conn):
    result = audit_db.audit_balance_equation(conn, rel_tolerance=0.01)
    assert len(result) == 1
    assert result[0]["stock_code"] == "000001"
    assert result[0]["report_period"] == "2023FY"


def test_audit_cross_table_consistency_detects_net_profit_mismatch(conn):
    result = audit_db.audit_cross_table_consistency(conn, rel_tolerance=0.01)
    assert len(result) >= 1
    match = next((r for r in result if r["stock_code"] == "000002" and r["report_period"] == "2024FY"), None)
    assert match is not None


def test_audit_missing_periods_when_expected_list_provided(conn):
    expected = [("000001", p) for p in ("2023FY", "2024FY", "2025FY")] + \
               [("000002", p) for p in ("2023FY", "2024FY", "2025FY")]
    result = audit_db.audit_missing_periods(conn, expected)
    missing = {(r["stock_code"], r["report_period"]) for r in result}
    assert missing == {("000001", "2025FY"), ("000002", "2025FY")}


def test_audit_yoy_outliers_flags_extreme_growth(conn):
    conn.execute(
        "UPDATE income_sheet SET net_profit_yoy_growth = 66500.0 WHERE stock_code='000002' AND report_period='2024FY'"
    )
    conn.commit()
    result = audit_db.audit_yoy_outliers(conn, revenue_threshold=500.0, profit_threshold=1000.0)
    matches = [r for r in result if r["stock_code"] == "000002" and r["report_period"] == "2024FY"]
    assert len(matches) == 1


def test_run_audit_returns_all_six_dimensions(conn):
    full = audit_db.run_audit(conn, expected_periods=None)
    for key in ("coverage", "null_rates", "balance_equation", "cross_table_consistency", "missing_periods", "yoy_outliers"):
        assert key in full
