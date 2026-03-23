from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pipeline import run_answer, run_etl
from config import REPORTS_DIR
from src.etl.loader import ETLLoader
from src.etl.pdf_parser import PDFParser
from src.etl.table_extractor import TableExtractor
from src.query.conversation import ConversationManager
from src.query.text2sql import Text2SQLEngine


def test_pdf_parser_confirmation_and_invalid_filter() -> None:
    parser = PDFParser()
    annual = parser.parse(REPORTS_DIR / "reports-上交所" / "600080_20240427_0WKP.pdf")
    classified = [t for t in annual.tables if t.table_type]
    assert any(t.table_type == "balance_sheet" and "货币资金" in "".join(str(c) for row in t.raw_rows[:10] for c in row if c) for t in classified)
    assert any(t.table_type == "income_sheet" and ("营业收入" in "".join(str(c) for row in t.raw_rows[:10] for c in row if c) or "营业总收入" in "".join(str(c) for row in t.raw_rows[:10] for c in row if c)) for t in classified)
    assert any(t.table_type == "cash_flow_sheet" and "销售商品" in "".join(str(c) for row in t.raw_rows[:15] for c in row if c) for t in classified)
    assert not any("母公司" in "".join(str(c) for row in t.raw_rows[:5] for c in row if c) and t.table_type in {"balance_sheet", "income_sheet", "cash_flow_sheet"} for t in classified)


def test_cross_page_merge_and_core_metrics_extraction() -> None:
    parser = PDFParser()
    extractor = TableExtractor()
    parsed = parser.parse(REPORTS_DIR / "reports-深交所" / "华润三九：2023年年度报告.pdf")
    records, _ = extractor.extract(parsed)
    balance_pages = [t.page_number for t in parsed.tables if t.table_type == "balance_sheet"]
    assert len(balance_pages) == 1
    assert records["core_performance_indicators_sheet"].get("total_operating_revenue") is not None or records["income_sheet"].get("total_operating_revenue") is not None


def test_income_sheet_coverage_over_80_for_both_companies() -> None:
    parser = PDFParser()
    extractor = TableExtractor()
    targets = [
        REPORTS_DIR / "reports-深交所" / "华润三九：2023年年度报告.pdf",
        REPORTS_DIR / "reports-上交所" / "600080_20240427_0WKP.pdf",
    ]
    for path in targets:
        records, _ = extractor.extract(parser.parse(path))
        row = records["income_sheet"]
        fields = [k for k in row if k not in {"serial_number", "stock_code", "stock_abbr", "report_period", "report_year"}]
        coverage = sum(1 for k in fields if row.get(k) is not None) / len(fields)
        assert coverage > 0.8, (path.name, coverage)


def test_etl_quality_regressions_for_target_reports() -> None:
    parser = PDFParser()
    extractor = TableExtractor()

    hz_2024hy = extractor.extract(parser.parse(REPORTS_DIR / "reports-深交所" / "华润三九：2024年半年度报告.pdf"))[0]
    assert hz_2024hy["balance_sheet"].get("liability_total_liabilities") is not None
    assert hz_2024hy["balance_sheet"].get("equity_total_equity") is not None

    for report_name in [
        "华润三九：2022年年度报告.pdf",
        "华润三九：2024年年度报告.pdf",
        "华润三九：2025年一季度报告.pdf",
        "华润三九：2025年三季度报告.pdf",
    ]:
        records, _ = extractor.extract(parser.parse(REPORTS_DIR / "reports-深交所" / report_name))
        core = records["core_performance_indicators_sheet"]
        assert core.get("eps") is not None, report_name
        assert core.get("roe") is not None, report_name

    hz_2023q3 = extractor.extract(parser.parse(REPORTS_DIR / "reports-深交所" / "华润三九：2023年三季度报告.pdf"))[0]
    assert hz_2023q3["income_sheet"].get("net_profit") is not None

    jh_2024q3 = extractor.extract(parser.parse(REPORTS_DIR / "reports-上交所" / "600080_20241030_XN72.pdf"))[0]
    assert jh_2024q3["income_sheet"].get("net_profit") is not None


def test_run_etl_all_reports_and_key_fields_non_null(tmp_path: Path) -> None:
    db_path = tmp_path / "finance.db"
    summary = run_etl(str(REPORTS_DIR), str(db_path))
    assert summary["loaded"] >= 13
    with sqlite3.connect(db_path) as conn:
        income_non_null = conn.execute("SELECT COUNT(*) FROM income_sheet WHERE total_operating_revenue IS NOT NULL AND total_profit IS NOT NULL").fetchone()[0]
        balance_non_null = conn.execute("SELECT COUNT(*) FROM balance_sheet WHERE asset_total_assets IS NOT NULL AND liability_total_liabilities IS NOT NULL").fetchone()[0]
        assert income_non_null >= 10
        assert balance_non_null >= 10


def _seed_answer_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE income_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, total_profit REAL, net_profit REAL, total_operating_revenue REAL)")
    conn.execute("CREATE TABLE balance_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, asset_total_assets REAL)")
    conn.execute("CREATE TABLE cash_flow_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, net_cash_flow REAL)")
    conn.execute("CREATE TABLE core_performance_indicators_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, eps REAL)")
    conn.execute("INSERT INTO income_sheet VALUES (1, '600080', '金花股份', '2025Q3', 2025, 3140.0, 2500.0, 18000.0)")
    conn.execute("INSERT INTO income_sheet VALUES (1, '000999', '华润三九', '2024FY', 2024, 50000.0, 42000.0, 240000.0)")
    conn.commit()
    conn.close()


def test_text2sql_parameterized_and_end_to_end(tmp_path: Path) -> None:
    db_path = tmp_path / "answer.db"
    _seed_answer_db(db_path)
    engine = Text2SQLEngine(str(db_path))
    conv = ConversationManager()
    first = engine.query("金花股份利润总额是多少", conv)
    assert first.needs_clarification is True
    conv.add_user_message("金花股份利润总额是多少")
    conv.merge_intent(first.intent)
    conv.add_assistant_message("请补充报告期。")
    result = engine.query("2025年第三季度的", conv)
    assert result.error is None
    assert result.rows[0]["total_profit"] == 3140.0
    assert "stock_abbr = '金花股份'" in result.sql
    assert "report_period = '2025Q3'" in result.sql


def test_result_xlsx_format_validation(tmp_path: Path) -> None:
    db_path = tmp_path / "answer.db"
    _seed_answer_db(db_path)
    questions = tmp_path / "questions.xlsx"
    import pandas as pd
    pd.DataFrame([
        {"编号": "B1001", "问题类型": "multi", "问题": json.dumps([{"Q": "金花股份利润总额是多少"}, {"Q": "2025年第三季度的"}], ensure_ascii=False)},
        {"编号": "B1002", "问题类型": "single", "问题": json.dumps([{"Q": "华润三九2024年营业收入是多少"}], ensure_ascii=False)},
    ]).to_excel(questions, index=False)
    output = tmp_path / "result_2.xlsx"
    run_answer(str(questions), str(db_path), str(output))
    df = __import__("pandas").read_excel(output)
    assert list(df.columns) == ["编号", "问题", "SQL查询语句", "图形格式", "回答"]
    assert set(df["编号"]) == {"B1001", "B1002"}


def test_end_to_end_b1001_b1002(tmp_path: Path) -> None:
    db_path = tmp_path / "answer.db"
    _seed_answer_db(db_path)
    questions = tmp_path / "questions.xlsx"
    import pandas as pd
    pd.DataFrame([
        {"编号": "B1001", "问题类型": "multi", "问题": json.dumps([{"Q": "金花股份利润总额是多少"}, {"Q": "2025年第三季度的"}], ensure_ascii=False)},
        {"编号": "B1002", "问题类型": "single", "问题": json.dumps([{"Q": "华润三九2024年营业收入是多少"}], ensure_ascii=False)},
    ]).to_excel(questions, index=False)
    output = tmp_path / "result_2.xlsx"
    run_answer(str(questions), str(db_path), str(output))
    df = __import__("pandas").read_excel(output)
    answer1 = df.loc[df["编号"] == "B1001", "回答"].iloc[0]
    answer2 = df.loc[df["编号"] == "B1002", "回答"].iloc[0]
    assert "3140" in answer1
    assert "240000" in answer2 or "24.00亿元" in answer2
