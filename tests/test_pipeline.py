from pathlib import Path
import json
import sqlite3

import pandas as pd

from pipeline import run_answer
from src.query.constants import USER_VISIBLE_WARNING_WHITELIST


def test_pipeline_answer_end_to_end(tmp_path: Path):
    db_path = tmp_path / "finance.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE income_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, total_profit REAL, total_operating_revenue REAL)")
    conn.execute("CREATE TABLE balance_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, asset_total_assets REAL)")
    conn.execute("CREATE TABLE cash_flow_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, net_cash_flow REAL)")
    conn.execute("CREATE TABLE core_performance_indicators_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, eps REAL)")
    conn.execute("INSERT INTO income_sheet VALUES (1, '600080', '金花股份', '2025Q3', 2025, 3140.0, 18000.0)")
    conn.commit()
    conn.close()

    questions = tmp_path / "questions.xlsx"
    pd.DataFrame([
        {"编号": "B1001", "问题类型": "multi", "问题": json.dumps([{"Q": "金花股份利润总额是多少"}, {"Q": "2025年第三季度的"}], ensure_ascii=False)}
    ]).to_excel(questions, index=False)

    output = tmp_path / "result_2.xlsx"
    run_answer(str(questions), str(db_path), str(output))
    assert output.exists()


def test_pipeline_answer_falls_back_when_llm_init_fails(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "finance.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE income_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, total_profit REAL, total_operating_revenue REAL)")
    conn.execute("CREATE TABLE balance_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, asset_total_assets REAL)")
    conn.execute("CREATE TABLE cash_flow_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, net_cash_flow REAL)")
    conn.execute("CREATE TABLE core_performance_indicators_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, eps REAL)")
    conn.execute("INSERT INTO income_sheet VALUES (1, '600080', '金花股份', '2025Q3', 2025, 3140.0, 18000.0)")
    conn.commit()
    conn.close()

    from src.llm import client as llm_client_module
    monkeypatch.setattr(llm_client_module.LLMClient, "from_env", classmethod(lambda cls: (_ for _ in ()).throw(RuntimeError("missing key"))))

    questions = tmp_path / "questions.xlsx"
    pd.DataFrame([
        {"编号": "B1002", "问题类型": "single", "问题": json.dumps([{"Q": "金花股份2025年第三季度利润总额是多少"}], ensure_ascii=False)}
    ]).to_excel(questions, index=False)

    output = tmp_path / "result_2.xlsx"
    run_answer(str(questions), str(db_path), str(output))
    result_df = pd.read_excel(output)
    assert output.exists()
    assert "SELECT" in result_df.loc[0, "SQL查询语句"]
    assert "total_profit" in result_df.loc[0, "SQL查询语句"]
    assert "income_sheet" in result_df.loc[0, "SQL查询语句"]



def test_pipeline_answer_sql_is_scoped_per_question_group(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "finance.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE income_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, total_profit REAL, total_operating_revenue REAL)")
    conn.execute("CREATE TABLE balance_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, asset_total_assets REAL)")
    conn.execute("CREATE TABLE cash_flow_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, net_cash_flow REAL)")
    conn.execute("CREATE TABLE core_performance_indicators_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, eps REAL)")
    conn.commit()
    conn.close()

    from src.query import text2sql as text2sql_module

    original_query_result = text2sql_module.QueryResult

    def fake_query(self, question, conversation=None):
        company = "金花股份" if "金花股份" in conversation.render() else "华润三九"
        sql = f"SELECT total_profit FROM income_sheet WHERE stock_abbr = '{company}' AND report_period = '2025Q3'"
        return original_query_result(
            sql=sql,
            rows=[{"total_profit": 1.0}],
            intent={"companies": [company], "fields": ["total_profit"], "periods": ["2025Q3"], "tables": ["income_sheet"]},
        )

    monkeypatch.setattr(text2sql_module.Text2SQLEngine, "query", fake_query)

    questions = tmp_path / "questions.xlsx"
    pd.DataFrame([
        {"编号": "B2001", "问题类型": "multi", "问题": json.dumps([{"Q": "金花股份2025年第三季度利润总额是多少"}, {"Q": "2025年第三季度的"}], ensure_ascii=False)},
        {"编号": "B2002", "问题类型": "multi", "问题": json.dumps([{"Q": "华润三九2025年第三季度利润总额是多少"}, {"Q": "2025年第三季度的"}], ensure_ascii=False)},
    ]).to_excel(questions, index=False)

    output = tmp_path / "result_2.xlsx"
    run_answer(str(questions), str(db_path), str(output))
    result_df = pd.read_excel(output)
    # First group should have 金花股份 SQL, second should have 华润三九 SQL
    assert "金花股份" in result_df.loc[0, "SQL查询语句"]
    assert "华润三九" in result_df.loc[1, "SQL查询语句"]



def test_pipeline_answer_catches_unhandled_query_errors(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "finance.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE income_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, total_profit REAL, total_operating_revenue REAL)")
    conn.execute("CREATE TABLE balance_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, asset_total_assets REAL)")
    conn.execute("CREATE TABLE cash_flow_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, net_cash_flow REAL)")
    conn.execute("CREATE TABLE core_performance_indicators_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, eps REAL)")
    conn.commit()
    conn.close()

    from src.query import text2sql as text2sql_module

    def boom(self, question, conversation=None):
        raise RuntimeError("llm timeout")

    monkeypatch.setattr(text2sql_module.Text2SQLEngine, "query", boom)

    questions = tmp_path / "questions.xlsx"
    pd.DataFrame([
        {"编号": "B1003", "问题类型": "single", "问题": json.dumps([{"Q": "任意问题"}], ensure_ascii=False)}
    ]).to_excel(questions, index=False)

    output = tmp_path / "result_2.xlsx"
    run_answer(str(questions), str(db_path), str(output))
    result_df = pd.read_excel(output)
    answer_payload = json.loads(result_df.loc[0, "回答"])
    assert answer_payload[0]["A"]["content"] == "查询失败：llm timeout"


def test_pipeline_answer_only_appends_whitelisted_warning_and_keeps_chart(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "finance.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE income_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, total_profit REAL, total_operating_revenue REAL)")
    conn.execute("CREATE TABLE balance_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, asset_total_assets REAL)")
    conn.execute("CREATE TABLE cash_flow_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, net_cash_flow REAL)")
    conn.execute("CREATE TABLE core_performance_indicators_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, eps REAL)")
    conn.commit()
    conn.close()

    from src.query import text2sql as text2sql_module

    def fake_query(self, question, conversation=None):
        return text2sql_module.QueryResult(
            sql="SELECT report_period, total_profit FROM income_sheet",
            rows=[
                {"report_period": "2023FY", "total_profit": 100.0},
                {"report_period": "2024FY", "total_profit": 120.0},
            ],
            intent={"tables": ["income_sheet"], "fields": ["total_profit"]},
            warning=USER_VISIBLE_WARNING_WHITELIST[0],
        )

    monkeypatch.setattr(text2sql_module.Text2SQLEngine, "query", fake_query)

    questions = tmp_path / "questions.xlsx"
    pd.DataFrame([
        {"编号": "B1005", "问题类型": "single", "问题": json.dumps([{"Q": "请查询同比情况"}], ensure_ascii=False)}
    ]).to_excel(questions, index=False)

    output = tmp_path / "result_2.xlsx"
    run_answer(str(questions), str(db_path), str(output))
    result_df = pd.read_excel(output)
    answer_payload = json.loads(result_df.loc[0, "回答"])
    assert f"（注：{USER_VISIBLE_WARNING_WHITELIST[0]}）" in answer_payload[0]["A"]["content"]


def test_pipeline_answer_hides_non_whitelisted_warning_from_user_output(tmp_path: Path, monkeypatch, caplog):
    db_path = tmp_path / "finance.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE income_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, total_profit REAL, total_operating_revenue REAL)")
    conn.execute("CREATE TABLE balance_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, asset_total_assets REAL)")
    conn.execute("CREATE TABLE cash_flow_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, net_cash_flow REAL)")
    conn.execute("CREATE TABLE core_performance_indicators_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, eps REAL)")
    conn.commit()
    conn.close()

    from src.query import text2sql as text2sql_module

    hidden_warning = "原始问题本身是一个待补充/澄清的提问模板，当前结果仅供参考。"

    def fake_query(self, question, conversation=None):
        return text2sql_module.QueryResult(
            sql="SELECT total_profit FROM income_sheet",
            rows=[{"total_profit": 100.0}],
            intent={"tables": ["income_sheet"], "fields": ["total_profit"]},
            warning=hidden_warning,
        )

    monkeypatch.setattr(text2sql_module.Text2SQLEngine, "query", fake_query)

    questions = tmp_path / "questions.xlsx"
    pd.DataFrame([
        {"编号": "B1005", "问题类型": "single", "问题": json.dumps([{"Q": "金花股份利润总额是多少"}], ensure_ascii=False)}
    ]).to_excel(questions, index=False)

    output = tmp_path / "result_2.xlsx"
    with caplog.at_level("INFO"):
        run_answer(str(questions), str(db_path), str(output))
    result_df = pd.read_excel(output)
    answer_payload = json.loads(result_df.loc[0, "回答"])
    assert hidden_warning not in answer_payload[0]["A"]["content"]
    assert f"Query warning: {hidden_warning}" in caplog.text


def test_pipeline_answer_hides_similar_but_non_whitelisted_yoy_warning(tmp_path: Path, monkeypatch, caplog):
    db_path = tmp_path / "finance.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE income_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, total_profit REAL, total_operating_revenue REAL)")
    conn.execute("CREATE TABLE balance_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, asset_total_assets REAL)")
    conn.execute("CREATE TABLE cash_flow_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, net_cash_flow REAL)")
    conn.execute("CREATE TABLE core_performance_indicators_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, eps REAL)")
    conn.commit()
    conn.close()

    from src.query import text2sql as text2sql_module

    hidden_warning = "上年同期数据不存在，但系统已自动回退到近似口径。"

    def fake_query(self, question, conversation=None):
        return text2sql_module.QueryResult(
            sql="SELECT net_profit FROM income_sheet",
            rows=[{"net_profit": 100.0}],
            intent={"tables": ["income_sheet"], "fields": ["net_profit"]},
            warning=hidden_warning,
        )

    monkeypatch.setattr(text2sql_module.Text2SQLEngine, "query", fake_query)

    questions = tmp_path / "questions.xlsx"
    pd.DataFrame([
        {"编号": "B1006", "问题类型": "single", "问题": json.dumps([{"Q": "华润三九2024年净利润同比"}], ensure_ascii=False)}
    ]).to_excel(questions, index=False)

    output = tmp_path / "result_2.xlsx"
    with caplog.at_level("INFO"):
        run_answer(str(questions), str(db_path), str(output))
    result_df = pd.read_excel(output)
    answer_payload = json.loads(result_df.loc[0, "回答"])
    assert hidden_warning not in answer_payload[0]["A"]["content"]
    assert f"Query warning: {hidden_warning}" in caplog.text
