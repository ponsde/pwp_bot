from pathlib import Path

from pipeline import run_etl
from src.etl.pdf_parser import PDFParser
from src.etl.table_extractor import TableExtractor


class DummyLoader:
    def __init__(self, *_args, **_kwargs):
        pass

    def load_pdf(self, pdf_path):
        name = Path(pdf_path).name
        if name == "loaded.pdf":
            return {"status": "loaded", "file": str(pdf_path)}
        if name == "rejected.pdf":
            return {"status": "rejected", "file": str(pdf_path), "warnings": ["bad data"]}
        raise RuntimeError("boom")


def test_infer_sse_period_from_filename_date_is_conservative() -> None:
    parser = PDFParser()

    assert parser._infer_sse_period_from_filename_date("20240331") == (2024, "2024Q1", False)
    assert parser._infer_sse_period_from_filename_date("20240430") == (2023, "2023FY", False)
    assert parser._infer_sse_period_from_filename_date("20240715") == (2024, "2024HY", False)
    assert parser._infer_sse_period_from_filename_date("20240831") == (2024, "2024HY", False)
    assert parser._infer_sse_period_from_filename_date("20241030") == (2024, "2024Q3", False)

    try:
        parser._infer_sse_period_from_filename_date("20241201")
    except ValueError as exc:
        assert "Cannot infer SSE report period" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported SSE filename month")


def test_gross_profit_margin_is_not_derived_from_zero_cost_of_sales() -> None:
    extractor = TableExtractor()
    records = {
        "income_sheet": {
            "serial_number": 1,
            "stock_code": "000001",
            "stock_abbr": "测试",
            "report_period": "2024FY",
            "report_year": 2024,
            "total_operating_revenue": 100.0,
            "operating_expense_cost_of_sales": 0.0,
        },
        "balance_sheet": {
            "serial_number": 1,
            "stock_code": "000001",
            "stock_abbr": "测试",
            "report_period": "2024FY",
            "report_year": 2024,
        },
        "cash_flow_sheet": {
            "serial_number": 1,
            "stock_code": "000001",
            "stock_abbr": "测试",
            "report_period": "2024FY",
            "report_year": 2024,
        },
        "core_performance_indicators_sheet": {
            "serial_number": 1,
            "stock_code": "000001",
            "stock_abbr": "测试",
            "report_period": "2024FY",
            "report_year": 2024,
        },
    }

    extractor._compute_derived_fields(records)

    assert "gross_profit_margin" not in records["core_performance_indicators_sheet"]


def test_balance_aliases_do_not_map_absorbed_deposits_to_contract_liabilities() -> None:
    extractor = TableExtractor()
    parsed = type("Parsed", (), {
        "stock_code": "000001",
        "stock_abbr": "测试银行",
        "report_period": "2024FY",
        "report_year": 2024,
        "page_texts": ["单位：万元"],
        "tables": [
            type("Table", (), {
                "table_type": "balance_sheet",
                "title": "合并资产负债表",
                "text": "单位：万元",
                "raw_rows": [["吸收存款", "1,000"]],
                "page_number": 1,
            })()
        ],
    })()

    records, _ = extractor.extract(parsed)

    assert "liability_contract_liabilities" not in records["balance_sheet"]


def test_run_etl_summary_reports_errors_and_completed_with_errors(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    for name in ("loaded.pdf", "rejected.pdf", "error.pdf"):
        (input_dir / name).write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr("src.etl.loader.ETLLoader", DummyLoader)

    summary = run_etl(str(input_dir), str(tmp_path / "test.db"))

    assert summary["processed"] == 3
    assert summary["loaded"] == 1
    assert summary["rejected"] == 1
    assert summary["error"] == 1
    assert summary["status"] == "completed_with_errors"
