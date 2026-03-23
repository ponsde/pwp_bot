from pathlib import Path
import json
import sqlite3

import pandas as pd

from pipeline import run_answer


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
