from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pipeline import run_answer, run_etl
from config import REPORTS_DIR
from src.etl.loader import ETLLoader
from src.etl.pdf_parser import PDFParser, ParsedPDF, ParsedTable
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


def test_core_derived_fields_and_flexible_aliases() -> None:
    extractor = TableExtractor()
    records = {
        "income_sheet": {
            "serial_number": 1,
            "stock_code": "000001",
            "stock_abbr": "示例",
            "report_period": "2025Q1",
            "report_year": 2025,
            "total_operating_revenue": 1000.0,
            "operating_expense_cost_of_sales": 600.0,
            "net_profit": 120.0,
        },
        "balance_sheet": {
            "serial_number": 1,
            "stock_code": "000001",
            "stock_abbr": "示例",
            "report_period": "2025Q1",
            "report_year": 2025,
            "asset_total_assets": 2000.0,
            "liability_total_liabilities": 800.0,
            "equity_total_equity": 1200.0,
            "share_capital": 5000000.0,
        },
        "cash_flow_sheet": {
            "serial_number": 1,
            "stock_code": "000001",
            "stock_abbr": "示例",
            "report_period": "2025Q1",
            "report_year": 2025,
            "operating_cf_net_amount": 250.0,
        },
        "core_performance_indicators_sheet": {
            "serial_number": 1,
            "stock_code": "000001",
            "stock_abbr": "示例",
            "report_period": "2025Q1",
            "report_year": 2025,
            "net_profit_excl_non_recurring": 100.0,
        },
    }
    extractor._compute_derived_fields(records)
    core = records["core_performance_indicators_sheet"]
    assert core["total_operating_revenue"] == 1000.0
    assert core["net_profit_10k_yuan"] == 120.0
    assert core["gross_profit_margin"] == 40.0
    assert core["net_profit_margin"] == 12.0
    assert core["roe"] == 10.0
    assert core["roe_weighted_excl_non_recurring"] == 8.3333
    assert core["operating_cf_per_share"] == 0.5
    assert core["net_asset_per_share"] == 2.4

    assert extractor._normalize_label("归属于上市公司股东的每股净资产（元/股）") == "归属于上市公司股东的每股净资产"
    assert extractor._normalize_label("基本每股收益（元/股）") == "基本每股收益"
    assert extractor._normalize_label("实收资本（或股本）") == "实收资本"


def test_target_report_regressions_for_coverage_optimization() -> None:
    parser = PDFParser()
    extractor = TableExtractor()

    hz_2024fy = extractor.extract(parser.parse(REPORTS_DIR / "reports-深交所" / "华润三九：2024年年度报告.pdf"))[0]
    core_2024fy = hz_2024fy["core_performance_indicators_sheet"]
    assert core_2024fy.get("roe") is not None
    assert core_2024fy.get("gross_profit_margin") is not None
    assert core_2024fy.get("net_profit_margin") is not None
    assert core_2024fy.get("total_operating_revenue") is not None
    assert core_2024fy.get("net_profit_10k_yuan") is not None
    assert core_2024fy.get("eps") is not None
    assert core_2024fy.get("net_profit_excl_non_recurring") is not None

    hz_2025q1 = extractor.extract(parser.parse(REPORTS_DIR / "reports-深交所" / "华润三九：2025年一季度报告.pdf"))[0]
    core_2025q1 = hz_2025q1["core_performance_indicators_sheet"]
    assert core_2025q1.get("total_operating_revenue") == hz_2025q1["income_sheet"].get("total_operating_revenue")
    assert core_2025q1.get("net_profit_margin") is not None

    jh_2024q3 = extractor.extract(parser.parse(REPORTS_DIR / "reports-上交所" / "600080_20241030_XN72.pdf"))[0]
    assert jh_2024q3["balance_sheet"].get("equity_total_equity") is not None
    assert jh_2024q3["income_sheet"].get("operating_expense_taxes_and_surcharges") is not None
    assert jh_2024q3["income_sheet"].get("total_operating_expenses") is not None
    assert jh_2024q3["core_performance_indicators_sheet"].get("operating_cf_per_share") is not None
    assert jh_2024q3["core_performance_indicators_sheet"].get("eps") is not None
    assert jh_2024q3["core_performance_indicators_sheet"].get("net_profit_excl_non_recurring") is not None


def test_extract_core_multiline_labels_with_inline_numbers() -> None:
    extractor = TableExtractor()
    table = ParsedTable(
        page_number=1,
        title="主要会计数据",
        table_type="core_performance_indicators_sheet",
        raw_rows=[
            ["项目", "2024年", "2023年"],
            ["基本每股收", "2.63", "2.15"],
            ["益（元/股）", None, None],
            ["归属于上市公司股东的扣除非经常", "311,786,734.83", "271,098,420.40"],
            ["性损益的净利润（元）", None, None],
            ["归属于上市公司股东的每股净资产", "14.56", "13.20"],
        ],
        text="单位：元",
    )
    target = {"serial_number": 1, "stock_code": "000001", "stock_abbr": "示例", "report_period": "2024FY", "report_year": 2024}
    extractor._extract_core_metrics(table, target, "2024FY", "元", [])
    assert target["eps"] == 2.63
    assert target["net_profit_excl_non_recurring"] == 31178.67
    assert target["net_asset_per_share"] == 14.56


def test_fill_income_net_profit_from_page_text_when_table_truncated() -> None:
    extractor = TableExtractor()
    parsed = ParsedPDF(
        file_path=Path("dummy.pdf"),
        exchange="SZSE",
        stock_code="000999",
        stock_abbr="华润三九",
        report_period="2023Q3",
        report_year=2023,
        is_summary=False,
        page_texts=["", "五、净利润（净亏损以“－”号填列） 2,695,179,086.81 1,978,188,001.45\n（二）按所有权归属分类\n1.归属于母公司股东的净利润（净亏损以“-”号填列） 2,402,599,847.04 1,952,336,233.90"],
        tables=[],
    )
    target = {"serial_number": 1, "stock_code": "000999", "stock_abbr": "华润三九", "report_period": "2023Q3", "report_year": 2023}
    extractor._fill_income_sheet_from_page_text(parsed, target)
    assert target["net_profit"] == 240259.98


def test_cashflow_net_cash_flow_is_normalized_to_10k_yuan() -> None:
    extractor = TableExtractor()
    table = ParsedTable(
        page_number=1,
        title="合并现金流量表",
        table_type="cash_flow_sheet",
        raw_rows=[
            ["项目", "本期发生额"],
            ["现金及现金等价物净增加额", "3,853,676,935"],
            ["经营活动产生的现金流量净额", "4,191,740,000"],
            ["投资活动产生的现金流量净额", "-120,000,000"],
        ],
        text="单位：元",
    )
    target = {"serial_number": 1, "stock_code": "000999", "stock_abbr": "华润三九", "report_period": "2025Q3", "report_year": 2025}
    extractor._extract_statement_table(table, "cash_flow_sheet", target, "元", [])
    assert target["net_cash_flow"] == 385367.69
    assert target["operating_cf_net_amount"] == 419174.0
    assert target["investing_cf_net_amount"] == -12000.0


def test_compute_derived_fields_overrides_q3_core_revenue_with_income_ytd() -> None:
    extractor = TableExtractor()
    records = {
        "income_sheet": {
            "serial_number": 1,
            "stock_code": "000999",
            "stock_abbr": "华润三九",
            "report_period": "2025Q3",
            "report_year": 2025,
            "total_operating_revenue": 1860800.0,
            "net_profit": 120000.0,
        },
        "balance_sheet": {
            "serial_number": 1,
            "stock_code": "000999",
            "stock_abbr": "华润三九",
            "report_period": "2025Q3",
            "report_year": 2025,
        },
        "cash_flow_sheet": {
            "serial_number": 1,
            "stock_code": "000999",
            "stock_abbr": "华润三九",
            "report_period": "2025Q3",
            "report_year": 2025,
        },
        "core_performance_indicators_sheet": {
            "serial_number": 1,
            "stock_code": "000999",
            "stock_abbr": "华润三九",
            "report_period": "2025Q3",
            "report_year": 2025,
            "total_operating_revenue": 546188.0,
        },
    }
    extractor._compute_derived_fields(records)
    assert records["core_performance_indicators_sheet"]["total_operating_revenue"] == 1860800.0


def test_loader_postprocess_fallback_fields(tmp_path: Path) -> None:
    loader = ETLLoader(tmp_path / "fallback.db")
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE core_performance_indicators_sheet (stock_code TEXT, report_period TEXT, net_profit_10k_yuan REAL, roe REAL, net_asset_per_share REAL)")
        conn.execute("CREATE TABLE balance_sheet (stock_code TEXT, report_period TEXT, report_year INTEGER, equity_total_equity REAL)")
        loader._ensure_share_capital_cache_table(conn)
        conn.executemany(
            "INSERT INTO balance_sheet VALUES (?, ?, ?, ?)",
            [
                ("000001", "2024FY", 2024, 200.0),
                ("000001", "2025Q1", 2025, None),
                ("000002", "2025Q1", 2025, None),
            ],
        )
        conn.executemany(
            "INSERT INTO _share_capital_cache VALUES (?, ?, ?)",
            [
                ("000001", "2024FY", 1000000.0),
            ],
        )
        conn.executemany(
            "INSERT INTO core_performance_indicators_sheet VALUES (?, ?, ?, ?, ?)",
            [
                ("000001", "2025Q1", 20.0, None, None),
                ("000002", "2025Q1", 30.0, None, None),
            ],
        )
        loader._postprocess_fallback_fields(conn)
        filled = conn.execute("SELECT roe, net_asset_per_share FROM core_performance_indicators_sheet WHERE stock_code='000001' AND report_period='2025Q1'").fetchone()
        missing = conn.execute("SELECT roe, net_asset_per_share FROM core_performance_indicators_sheet WHERE stock_code='000002' AND report_period='2025Q1'").fetchone()
        assert filled == (10.0, 2.0)
        assert missing == (None, None)


def test_loader_postprocess_fallback_fields_uses_current_period_balance_and_share_capital(tmp_path: Path) -> None:
    loader = ETLLoader(tmp_path / "fallback_current.db")
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE core_performance_indicators_sheet (stock_code TEXT, report_period TEXT, net_profit_10k_yuan REAL, roe REAL, net_asset_per_share REAL)")
        conn.execute("CREATE TABLE balance_sheet (stock_code TEXT, report_period TEXT, report_year INTEGER, equity_total_equity REAL)")
        loader._ensure_share_capital_cache_table(conn)
        conn.execute("INSERT INTO balance_sheet VALUES (?, ?, ?, ?)", ("000001", "2025Q1", 2025, 250.0))
        conn.execute("INSERT INTO _share_capital_cache VALUES (?, ?, ?)", ("000001", "2025Q1", 500000.0))
        conn.execute("INSERT INTO core_performance_indicators_sheet VALUES (?, ?, ?, ?, ?)", ("000001", "2025Q1", 25.0, None, None))
        loader._postprocess_fallback_fields(conn)
        filled = conn.execute("SELECT roe, net_asset_per_share FROM core_performance_indicators_sheet WHERE stock_code='000001' AND report_period='2025Q1'").fetchone()
        assert filled == (10.0, 5.0)


def test_loader_postprocess_yoy_qoq_growth(tmp_path: Path) -> None:
    loader = ETLLoader(tmp_path / "growth.db")
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE core_performance_indicators_sheet (stock_code TEXT, report_period TEXT, total_operating_revenue REAL, net_profit_10k_yuan REAL, net_profit_excl_non_recurring REAL, operating_revenue_yoy_growth REAL, net_profit_yoy_growth REAL, net_profit_excl_non_recurring_yoy REAL, operating_revenue_qoq_growth REAL, net_profit_qoq_growth REAL)")
        conn.execute("CREATE TABLE balance_sheet (stock_code TEXT, report_period TEXT, asset_total_assets REAL, liability_total_liabilities REAL, asset_total_assets_yoy_growth REAL, liability_total_liabilities_yoy_growth REAL)")
        conn.execute("CREATE TABLE income_sheet (stock_code TEXT, report_period TEXT, total_operating_revenue REAL, net_profit REAL, operating_revenue_yoy_growth REAL, net_profit_yoy_growth REAL)")
        conn.execute("CREATE TABLE cash_flow_sheet (stock_code TEXT, report_period TEXT, net_cash_flow REAL, net_cash_flow_yoy_growth REAL)")
        conn.executemany(
            "INSERT INTO core_performance_indicators_sheet VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL)",
            [
                ("000001", "2023FY", 100.0, 20.0, 18.0),
                ("000001", "2024Q3", 90.0, 18.0, 16.0),
                ("000001", "2024FY", 120.0, 30.0, 24.0),
            ],
        )
        conn.executemany(
            "INSERT INTO balance_sheet VALUES (?, ?, ?, ?, NULL, NULL)",
            [
                ("000001", "2023FY", 200.0, 80.0),
                ("000001", "2024FY", 260.0, 91.0),
            ],
        )
        conn.executemany(
            "INSERT INTO income_sheet VALUES (?, ?, ?, ?, NULL, NULL)",
            [
                ("000001", "2023FY", 1000.0, 150.0),
                ("000001", "2024FY", 1200.0, 180.0),
            ],
        )
        conn.executemany(
            "INSERT INTO cash_flow_sheet VALUES (?, ?, ?, NULL)",
            [
                ("000001", "2023FY", 50.0),
                ("000001", "2024FY", 65.0),
            ],
        )
        loader._postprocess_growth_fields(conn)
        row = conn.execute("SELECT operating_revenue_yoy_growth, net_profit_yoy_growth, net_profit_excl_non_recurring_yoy FROM core_performance_indicators_sheet WHERE stock_code='000001' AND report_period='2024FY'").fetchone()
        assert row == (20.0, 50.0, 33.3333)
        balance_row = conn.execute("SELECT asset_total_assets_yoy_growth, liability_total_liabilities_yoy_growth FROM balance_sheet WHERE stock_code='000001' AND report_period='2024FY'").fetchone()
        assert balance_row == (30.0, 13.75)
        income_row = conn.execute("SELECT operating_revenue_yoy_growth, net_profit_yoy_growth FROM income_sheet WHERE stock_code='000001' AND report_period='2024FY'").fetchone()
        assert income_row == (20.0, 20.0)
        cashflow_row = conn.execute("SELECT net_cash_flow_yoy_growth FROM cash_flow_sheet WHERE stock_code='000001' AND report_period='2024FY'").fetchone()
        assert cashflow_row == (30.0,)


def test_run_etl_all_reports_and_key_fields_non_null(tmp_path: Path) -> None:
    db_path = tmp_path / "finance.db"
    summary = run_etl(str(REPORTS_DIR), str(db_path))
    assert summary["loaded"] >= 13
    with sqlite3.connect(db_path) as conn:
        income_non_null = conn.execute("SELECT COUNT(*) FROM income_sheet WHERE total_operating_revenue IS NOT NULL AND total_profit IS NOT NULL").fetchone()[0]
        balance_non_null = conn.execute("SELECT COUNT(*) FROM balance_sheet WHERE asset_total_assets IS NOT NULL AND liability_total_liabilities IS NOT NULL").fetchone()[0]
        yoy_non_null = conn.execute("SELECT COUNT(*) FROM core_performance_indicators_sheet WHERE operating_revenue_yoy_growth IS NOT NULL OR net_profit_yoy_growth IS NOT NULL").fetchone()[0]
        assert income_non_null >= 10
        assert balance_non_null >= 10
        assert yoy_non_null >= 4


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
    assert "3140" in answer1 or "3,140" in answer1
    assert "240000" in answer2 or "240,000" in answer2 or "24.00亿元" in answer2
