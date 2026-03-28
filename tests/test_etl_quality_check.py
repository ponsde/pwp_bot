from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.etl_quality_check import (
    check_cross_table_consistency,
    check_ranges,
    check_yoy_validation,
    coverage_report,
)
from src.etl.schema import FieldMeta, load_schema_metadata
from src.etl.table_extractor import TableExtractor


def test_etl_quality_check_detects_issues_and_reports_coverage(tmp_path: Path) -> None:
    db_path = tmp_path / "quality.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE core_performance_indicators_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, eps REAL, total_operating_revenue REAL, net_profit_10k_yuan REAL, net_profit_excl_non_recurring REAL, operating_revenue_yoy_growth REAL, net_profit_yoy_growth REAL, net_profit_excl_non_recurring_yoy REAL, roe REAL, roe_weighted_excl_non_recurring REAL)"
        )
        conn.execute(
            "CREATE TABLE income_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, total_operating_revenue REAL, net_profit REAL, total_profit REAL, operating_revenue_yoy_growth REAL, net_profit_yoy_growth REAL)"
        )
        conn.execute(
            "CREATE TABLE cash_flow_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, net_cash_flow REAL, operating_cf_net_amount REAL, net_cash_flow_yoy_growth REAL)"
        )
        conn.execute(
            "CREATE TABLE balance_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, asset_total_assets REAL, liability_total_liabilities REAL, equity_total_equity REAL, asset_total_assets_yoy_growth REAL, liability_total_liabilities_yoy_growth REAL)"
        )
        conn.executemany(
            "INSERT INTO core_performance_indicators_sheet VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "000001", "示例", "2023FY", 2023, 0.5, 100.0, 10.0, 8.0, None, None, None, 5.0, 4.0),
                (1, "000001", "示例", "2024FY", 2024, 999.0, 120.0, 12.0, 9.0, 20.0, 20.0, 12.5, 6.0, 4.5),
            ],
        )
        conn.executemany(
            "INSERT INTO income_sheet VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "000001", "示例", "2023FY", 2023, 100.0, 10.0, 12.0, None, None),
                (1, "000001", "示例", "2024FY", 2024, 110.0, 12.0, 14.0, 20.0, 20.0),
            ],
        )
        conn.executemany(
            "INSERT INTO cash_flow_sheet VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "000001", "示例", "2023FY", 2023, 50.0, 40.0, None),
                (1, "000001", "示例", "2024FY", 2024, 75.0, 60.0, 50.0),
            ],
        )
        conn.executemany(
            "INSERT INTO balance_sheet VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "000001", "示例", "2023FY", 2023, 200.0, 80.0, 120.0, None, None),
                (1, "000001", "示例", "2024FY", 2024, 260.0, 91.0, 169.0, 30.0, 13.75),
            ],
        )

        range_issues = check_ranges(conn)
        cross_issues = check_cross_table_consistency(conn)
        yoy_issues = check_yoy_validation(conn)
        coverage = coverage_report(conn)

    assert any("core_performance_indicators_sheet.eps" in issue for issue in range_issues)
    assert any("revenue mismatch" in issue for issue in cross_issues)
    assert any("income_sheet.operating_revenue_yoy_growth" in issue for issue in yoy_issues)
    assert any(line.startswith("[coverage] core_performance_indicators_sheet rows=2") for line in coverage)


def test_net_cash_flow_schema_metadata_is_normalized_to_ten_thousand_yuan() -> None:
    metadata = load_schema_metadata()
    net_cash_flow_meta = next(field for field in metadata["cash_flow_sheet"] if field.name == "net_cash_flow")
    assert net_cash_flow_meta.unit == "万元"


def test_extract_income_value_from_page_text_accepts_common_separators() -> None:
    extractor = TableExtractor()
    samples = [
        "归属于母公司股东的净利润：123,456.78",
        "归属于母公司股东的净利润: 123,456.78",
        "归属于母公司股东的净利润 123,456.78",
    ]

    for sample in samples:
        assert extractor._extract_income_value_from_page_text([sample], "归属于母公司股东的净利润") == "123,456.78"
