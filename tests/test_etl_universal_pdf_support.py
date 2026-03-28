from pathlib import Path
import sqlite3

from pipeline import run_etl
from scripts.etl_quality_check import check_cross_table_consistency, check_ranges, check_yoy_validation
from src.etl.loader import ETLLoader
from src.etl.pdf_parser import PDFParser
from src.etl.table_extractor import TableExtractor


UNIVERSAL_REPORTS_DIR = Path("data/sample/示例数据/附件2：财务报告/reports-通用测试")


def test_universal_reports_extract_key_fields_for_moutai_and_pingan() -> None:
    parser = PDFParser()
    extractor = TableExtractor()

    moutai_records, _ = extractor.extract(parser.parse(UNIVERSAL_REPORTS_DIR / "贵州茅台：2023年年度报告.pdf"))
    moutai_core = moutai_records["core_performance_indicators_sheet"]
    assert moutai_core.get("eps") is not None
    assert moutai_core.get("total_operating_revenue") is not None
    assert moutai_core.get("net_profit_10k_yuan") is not None
    assert moutai_core.get("roe") is not None
    assert moutai_core.get("net_asset_per_share") is not None
    assert moutai_core.get("roe_weighted_excl_non_recurring") is not None
    assert moutai_core.get("operating_cf_per_share") is not None

    pingan_records, _ = extractor.extract(parser.parse(UNIVERSAL_REPORTS_DIR / "平安银行：2023年年度报告.pdf"))
    pingan_income = pingan_records["income_sheet"]
    pingan_cash = pingan_records["cash_flow_sheet"]
    pingan_balance = pingan_records["balance_sheet"]
    pingan_core = pingan_records["core_performance_indicators_sheet"]
    assert pingan_income.get("total_operating_revenue") is not None
    assert pingan_income.get("net_profit") is not None
    assert pingan_cash.get("operating_cf_net_amount") is not None
    assert pingan_cash.get("net_cash_flow") is not None
    assert pingan_balance.get("asset_total_assets") is not None
    assert pingan_balance.get("liability_total_liabilities") is not None
    assert pingan_balance.get("equity_total_equity") is not None
    assert pingan_core.get("total_operating_revenue") is not None
    assert pingan_core.get("net_profit_10k_yuan") is not None


def test_run_etl_universal_reports_is_resilient_and_quality_clean(tmp_path: Path) -> None:
    db_path = tmp_path / "universal.db"
    summary = run_etl(str(UNIVERSAL_REPORTS_DIR), str(db_path))

    assert summary["processed"] == 2
    assert summary["loaded"] == 2
    assert summary["skipped"] == 0
    assert summary["rejected"] == 0
    assert all("reason" in item for item in summary["results"])
    assert {item["status"] for item in summary["results"]} == {"loaded"}

    with sqlite3.connect(db_path) as conn:
        moutai_core = conn.execute(
            "SELECT eps, total_operating_revenue, net_profit_10k_yuan, roe FROM core_performance_indicators_sheet WHERE stock_code='600519' AND report_period='2023FY'"
        ).fetchone()
        assert moutai_core is not None
        assert all(value is not None for value in moutai_core)

        issues = []
        issues.extend(check_ranges(conn))
        issues.extend(check_cross_table_consistency(conn))
        issues.extend(check_yoy_validation(conn))
        assert issues == []


def test_loader_allows_incomplete_unknown_company_records(tmp_path: Path) -> None:
    loader = ETLLoader(tmp_path / "graceful.db")

    class DummyParser:
        def parse(self, pdf_path):
            return type("Parsed", (), {
                "is_summary": False,
                "stock_code": "999999",
                "stock_abbr": "未知公司",
                "report_period": "2023FY",
                "report_year": 2023,
            })()

    class DummyExtractor:
        def extract(self, parsed):
            base = {
                "serial_number": 1,
                "stock_code": parsed.stock_code,
                "stock_abbr": parsed.stock_abbr,
                "report_period": parsed.report_period,
                "report_year": parsed.report_year,
            }
            return {
                "core_performance_indicators_sheet": dict(base, total_operating_revenue=10.0),
                "balance_sheet": dict(base),
                "income_sheet": dict(base, net_profit=1.0),
                "cash_flow_sheet": dict(base),
            }, []

    loader.parser = DummyParser()
    loader.extractor = DummyExtractor()

    result = loader.load_pdf("dummy.pdf")
    assert result["status"] == "loaded"
    assert any("missing key fields" in warning for warning in result["warnings"])
