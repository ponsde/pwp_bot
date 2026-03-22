from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from config import REPORTS_DIR
from src.etl.loader import ETLLoader
from src.etl.pdf_parser import PDFParser
from src.etl.schema import create_tables, load_company_mapping, load_schema_metadata, validate_schema
from src.etl.table_extractor import TableExtractor
from src.etl.validator import DataValidator


@pytest.fixture()
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_financial_reports.db"


def test_schema_create_and_validate(temp_db: Path) -> None:
    metadata = create_tables(temp_db)
    validate_schema(temp_db, metadata)
    assert set(metadata) == {
        "core_performance_indicators_sheet",
        "balance_sheet",
        "income_sheet",
        "cash_flow_sheet",
    }
    assert any(field.name == "net_cash_flow" and field.unit == "元" for field in metadata["cash_flow_sheet"])
    assert any(field.name == "eps" and field.unit == "元" for field in metadata["core_performance_indicators_sheet"])


def test_company_mapping_loads() -> None:
    mapping = load_company_mapping()
    assert mapping["000999"]["stock_abbr"] == "华润三九"
    assert mapping["金花股份"]["stock_code"] == "600080"


def test_pdf_parser_identifies_szse_and_sse() -> None:
    parser = PDFParser()
    szse = parser.parse(REPORTS_DIR / "reports-深交所" / "华润三九：2023年年度报告.pdf")
    assert szse.stock_abbr == "华润三九"
    assert szse.report_period == "2023FY"
    assert not szse.is_summary
    assert {t.table_type for t in szse.tables if t.table_type} >= {
        "core_performance_indicators_sheet",
        "balance_sheet",
        "income_sheet",
        "cash_flow_sheet",
    }

    sse = parser.parse(REPORTS_DIR / "reports-上交所" / "600080_20240427_0WKP.pdf")
    assert sse.stock_code == "600080"
    assert sse.report_period == "2023FY"
    assert not sse.is_summary


def test_pdf_parser_distinguishes_sse_same_date_variants() -> None:
    parser = PDFParser()
    annual = parser.parse(REPORTS_DIR / "reports-上交所" / "600080_20240427_0WKP.pdf")
    q1 = parser.parse(REPORTS_DIR / "reports-上交所" / "600080_20240427_IBMB.pdf")
    summary = parser.parse(REPORTS_DIR / "reports-上交所" / "600080_20240427_W39O.pdf")
    assert annual.report_period == "2023FY"
    assert q1.report_period == "2024Q1"
    assert summary.is_summary is True


def test_table_extractor_maps_income_and_core_fields() -> None:
    parser = PDFParser()
    extractor = TableExtractor()

    cr = parser.parse(REPORTS_DIR / "reports-深交所" / "华润三九：2023年年度报告.pdf")
    records, warnings = extractor.extract(cr)
    assert records["income_sheet"]["total_operating_revenue"] > 0
    assert records["income_sheet"]["net_profit"] > 0
    assert records["cash_flow_sheet"]["net_cash_flow"] > 0
    assert records["balance_sheet"]["asset_total_assets"] > 0

    jf = parser.parse(REPORTS_DIR / "reports-上交所" / "600080_20240427_0WKP.pdf")
    jf_records, jf_warnings = extractor.extract(jf)
    assert jf_records["core_performance_indicators_sheet"]["total_operating_revenue"] > 0
    assert "net_profit_10k_yuan" in jf_records["core_performance_indicators_sheet"]
    assert isinstance(warnings + jf_warnings, list)


def test_validator_warns_but_not_blocking() -> None:
    validator = DataValidator()
    records = {
        "balance_sheet": {"report_period": "2023FY", "asset_total_assets": 100.0, "liability_total_liabilities": 80.0, "equity_total_equity": 10.0},
        "income_sheet": {"report_period": "2023FY", "net_profit": 50.0, "total_operating_revenue": 100.0, "total_operating_expenses": 90.0, "operating_profit": 5.0},
        "cash_flow_sheet": {"report_period": "bad"},
        "core_performance_indicators_sheet": {"report_period": "2023FY", "net_profit_10k_yuan": 10.0},
    }
    result = validator.validate(records)
    assert result.ok is True
    assert len(result.warnings) >= 2


def test_loader_integration_all_full_reports(temp_db: Path) -> None:
    loader = ETLLoader(temp_db)
    report_root = REPORTS_DIR
    pdf_files = sorted(report_root.rglob("*.pdf"))
    loaded = 0
    skipped = 0
    for pdf in pdf_files:
        result = loader.load_pdf(pdf)
        if result["status"] == "loaded":
            loaded += 1
        else:
            skipped += 1
    assert loaded == 13
    assert skipped == 5

    with sqlite3.connect(temp_db) as conn:
        for table in [
            "core_performance_indicators_sheet",
            "balance_sheet",
            "income_sheet",
            "cash_flow_sheet",
        ]:
            count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            assert count == 13
        row = conn.execute('SELECT stock_abbr, report_period, total_profit FROM income_sheet WHERE stock_code = ? AND report_period = ?', ("600080", "2023FY")).fetchone()
        assert row[0] == "金花股份"
        assert row[1] == "2023FY"
        assert row[2] is not None
