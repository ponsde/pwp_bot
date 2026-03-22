import sqlite3
from pathlib import Path

from src.query.conversation import ConversationManager
from src.query.text2sql import CREATE_TABLE_SQL, Text2SQLEngine


def make_db(tmp_path: Path) -> str:
    db_path = tmp_path / "finance.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(CREATE_TABLE_SQL)
    conn.execute(
        "INSERT INTO income_sheet VALUES (1, '600080', '金花股份', '2025Q3', 2025, 123000000, 31400000, 25000000)"
    )
    conn.commit()
    conn.close()
    return str(db_path)


def test_text2sql_clarify_when_period_missing(tmp_path: Path):
    engine = Text2SQLEngine(make_db(tmp_path))
    result = engine.query("金花股份利润总额是多少")
    assert result.needs_clarification is True
    assert "报告期" in result.clarification_question


def test_text2sql_query_success_with_conversation(tmp_path: Path):
    engine = Text2SQLEngine(make_db(tmp_path))
    conv = ConversationManager()
    conv.add_user_message("金花股份利润总额是多少")
    conv.add_assistant_message("请补充报告期。")
    result = engine.query("2025年第三季度的", conv)
    assert result.error is None
    assert result.rows[0]["total_profit"] == 31400000
    assert "report_period = '2025Q3'" in result.sql
