import json
import sqlite3
from pathlib import Path

import pandas as pd

from pipeline import run_research


class FakeResearchAnswer:
    def __init__(self, question):
        self.question = question
        self.route = 'rag'
        self.answer = '根据研报，国家医保目录新增多个中药产品。'
        self.sql = ''
        self.chart_type = 'bar'
        self.chart_rows = [{'report_period': '2025Q1', 'total_operating_revenue': 100.0}, {'report_period': '2025Q2', 'total_operating_revenue': 120.0}]
        self.references = [type('Ref', (), {'paper_path': './附件5：研报数据/个股研报/paper.pdf', 'text': '研报段落', 'paper_image': ''})()]


def test_pipeline_research_end_to_end(tmp_path: Path, monkeypatch):
    db_path = tmp_path / 'finance.db'
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE income_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, total_profit REAL, total_operating_revenue REAL)")
    conn.execute("CREATE TABLE balance_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, asset_total_assets REAL)")
    conn.execute("CREATE TABLE cash_flow_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, net_cash_flow REAL)")
    conn.execute("CREATE TABLE core_performance_indicators_sheet (serial_number INTEGER, stock_code TEXT, stock_abbr TEXT, report_period TEXT, report_year INTEGER, eps REAL)")
    conn.commit()
    conn.close()

    questions = tmp_path / 'questions.xlsx'
    pd.DataFrame([
        {'编号': 'B2002', '问题类型': '意图模糊', '问题': json.dumps([{'Q': '国家医保目录新增的中药产品有哪些并可视化展示'}], ensure_ascii=False)}
    ]).to_excel(questions, index=False)

    import pipeline as pipeline_module
    monkeypatch.setattr(pipeline_module, '_build_llm_client', lambda: None)
    monkeypatch.setattr('src.knowledge.ov_adapter.init_client', lambda data_path, config_path: object())

    class FakeQA:
        def __init__(self, db_path, client, llm_client=None):
            pass
        def answer_question(self, question, conversation=None):
            return FakeResearchAnswer(question)

    monkeypatch.setattr('src.knowledge.research_qa.ResearchQAEngine', FakeQA)
    monkeypatch.setattr('src.knowledge.research_loader.load_research_documents', lambda client: [])

    output = tmp_path / 'result_3.xlsx'
    run_research(str(questions), str(db_path), str(output))
    result_df = pd.read_excel(output)
    payload = json.loads(result_df.loc[0, '回答'])
    assert output.exists()
    assert payload[0]['references'][0]['paper_path'] == './附件5：研报数据/个股研报/paper.pdf'
    assert result_df.loc[0, '图形格式'] == 'bar'
    assert Path(payload[0]['image'][0]).exists()
