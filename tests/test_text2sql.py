import sqlite3
from pathlib import Path

from src.prompts.loader import load_prompt
from src.query.conversation import ConversationManager
from src.query.text2sql import CREATE_TABLE_SQL, Text2SQLEngine


def make_db(tmp_path: Path) -> str:
    db_path = tmp_path / "finance.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(CREATE_TABLE_SQL)
    conn.execute(
        "INSERT INTO income_sheet (serial_number, stock_code, stock_abbr, report_period, report_year, total_profit, net_profit, total_operating_revenue) VALUES (1, '600080', '金花股份', '2025Q3', 2025, 123000000, 31400000, 25000000)"
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
    first = engine.query("金花股份利润总额是多少", conv)
    assert first.needs_clarification is True
    conv.add_user_message("金花股份利润总额是多少")
    conv.merge_intent(first.intent)
    conv.add_assistant_message("请补充报告期。")
    result = engine.query("2025年第三季度的", conv)
    assert result.error is None
    assert result.rows[0]["total_profit"] == 123000000
    assert "report_period = '2025Q3'" in result.sql


def test_text2sql_blocks_non_select(tmp_path: Path):
    engine = Text2SQLEngine(make_db(tmp_path))
    try:
        engine._ensure_safe_sql("DELETE FROM income_sheet")
    except Exception as exc:
        assert "SELECT" in str(exc) or "不允许" in str(exc)
    else:
        raise AssertionError("non-select sql should be blocked")


def test_load_new_recovery_prompts():
    validate_content = load_prompt(
        "validate_result.md",
        question="金花股份2025年第三季度利润总额是多少",
        intent_json='{"tables": ["income_sheet"], "fields": ["total_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": false}',
        sql="SELECT total_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3'",
        rows_json='[{"total_profit": 123}]',
    )
    reflect_content = load_prompt(
        "reflect.md",
        question="金花股份2025年第三季度利润总额是多少",
        intent_json='{"tables": ["income_sheet"], "fields": ["total_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": false}',
        sql="SELECT total_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3'",
        rows_json='[{"total_profit": 123}]',
    )
    assert "金花股份2025年第三季度利润总额是多少" in validate_content
    assert "金花股份2025年第三季度利润总额是多少" in reflect_content


def test_second_layer_result_validation_regenerates_sql(tmp_path: Path):
    class StubLLM:
        def __init__(self):
            self.calls = []
            self.validation_count = 0

        def complete(self, prompt: str) -> str:
            self.calls.append(prompt)
            if "提取结构化查询意图" in prompt:
                return '{"tables": ["income_sheet"], "fields": ["total_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": false}'
            if "生成单条 SQL" in prompt:
                if "补充约束" in prompt:
                    return "```sql\nSELECT total_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
                return "```sql\nSELECT net_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
            if "结果校验器" in prompt:
                self.validation_count += 1
                if self.validation_count == 1:
                    return '{"accepted": false, "reason": "返回了净利润字段，不是利润总额字段。"}'
                return '{"accepted": true, "reason": ""}'
            if "任务反思器" in prompt:
                return '{"accepted": true, "reason": "", "rewritten_question": ""}'
            raise AssertionError(prompt)

    engine = Text2SQLEngine(make_db(tmp_path), llm_client=StubLLM())
    result = engine.query("金花股份2025年第三季度利润总额是多少")
    assert result.error is None
    assert result.sql and "total_profit" in result.sql
    assert result.rows[0]["total_profit"] == 123000000


def test_second_layer_result_validation_stops_after_one_retry(tmp_path: Path):
    class StubLLM:
        def __init__(self):
            self.validation_count = 0

        def complete(self, prompt: str) -> str:
            if "提取结构化查询意图" in prompt:
                return '{"tables": ["income_sheet"], "fields": ["total_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": false}'
            if "生成单条 SQL" in prompt:
                return "```sql\nSELECT net_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
            if "结果校验器" in prompt:
                self.validation_count += 1
                return '{"accepted": false, "reason": "仍然返回了错误字段。"}'
            if "任务反思器" in prompt:
                raise AssertionError("validation should fail before reflection")
            raise AssertionError(prompt)

    engine = Text2SQLEngine(make_db(tmp_path), llm_client=StubLLM())
    result = engine.query("金花股份2025年第三季度利润总额是多少")
    assert result.error == "仍然返回了错误字段。"


def test_third_layer_reflection_reanalyzes_intent(tmp_path: Path):
    class StubLLM:
        def __init__(self):
            self.reflect_count = 0

        def complete(self, prompt: str) -> str:
            if "提取结构化查询意图" in prompt:
                if "请查询金花股份2025年第三季度利润总额" in prompt:
                    return '{"tables": ["income_sheet"], "fields": ["total_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": false}'
                return '{"tables": ["income_sheet"], "fields": ["net_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": false}'
            if "生成单条 SQL" in prompt:
                if '"total_profit"' in prompt:
                    return "```sql\nSELECT total_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
                return "```sql\nSELECT net_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
            if "结果校验器" in prompt:
                return '{"accepted": true, "reason": ""}'
            if "任务反思器" in prompt:
                self.reflect_count += 1
                if self.reflect_count == 1:
                    return '{"accepted": false, "reason": "原始任务要查询利润总额，不是净利润。", "rewritten_question": "请查询金花股份2025年第三季度利润总额"}'
                return '{"accepted": true, "reason": "", "rewritten_question": ""}'
            raise AssertionError(prompt)

    engine = Text2SQLEngine(make_db(tmp_path), llm_client=StubLLM())
    result = engine.query("金花股份2025年第三季度盈利情况")
    assert result.error is None
    assert result.sql and "total_profit" in result.sql
    assert result.rows[0]["total_profit"] == 123000000
    assert result.intent["fields"] == ["total_profit"]


def test_third_layer_reflection_stops_after_one_retry(tmp_path: Path):
    class StubLLM:
        def __init__(self):
            self.reflect_count = 0

        def complete(self, prompt: str) -> str:
            if "提取结构化查询意图" in prompt:
                return '{"tables": ["income_sheet"], "fields": ["net_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": false}'
            if "生成单条 SQL" in prompt:
                return "```sql\nSELECT net_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
            if "结果校验器" in prompt:
                return '{"accepted": true, "reason": ""}'
            if "任务反思器" in prompt:
                self.reflect_count += 1
                return '{"accepted": false, "reason": "任务理解仍然错误。", "rewritten_question": "请查询金花股份2025年第三季度利润总额"}'
            raise AssertionError(prompt)

    engine = Text2SQLEngine(make_db(tmp_path), llm_client=StubLLM())
    result = engine.query("金花股份2025年第三季度盈利情况")
    assert result.error == "任务理解仍然错误。"


def test_query_with_recovery_keeps_input_intent_immutable(tmp_path: Path):
    engine = Text2SQLEngine(make_db(tmp_path))
    intent = {
        "tables": ["income_sheet"],
        "fields": ["total_profit"],
        "companies": ["金花股份"],
        "periods": ["2025Q3"],
        "is_trend": False,
    }
    snapshot = {k: (v.copy() if isinstance(v, list) else v) for k, v in intent.items()}

    sql, rows, final_intent = engine._query_with_recovery("金花股份2025年第三季度利润总额是多少", intent)

    assert sql and "total_profit" in sql
    assert rows[0]["total_profit"] == 123000000
    assert intent == snapshot
    assert final_intent == snapshot
