import sqlite3
from pathlib import Path

from src.llm.client import LLMClient
from src.prompts.loader import load_prompt
from src.query.conversation import ConversationManager
from src.query.text2sql import CREATE_TABLE_SQL, MAX_PROMPT_ROWS, Text2SQLEngine, UserFacingError


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


def make_multi_year_db(tmp_path: Path) -> str:
    """DB with 3 years of data for 华润三九 + multiple companies for top N."""
    db_path = tmp_path / "finance_multi.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(CREATE_TABLE_SQL)
    rows = [
        (1, '000999', '华润三九', '2022FY', 2022, 500000000, 300000000, 2000000000),
        (2, '000999', '华润三九', '2023FY', 2023, 600000000, 350000000, 2200000000),
        (3, '000999', '华润三九', '2024FY', 2024, 700000000, 400000000, 2500000000),
        (4, '600080', '金花股份', '2023FY', 2023, 60000000, 30000000, 420000000),
        (5, '600080', '金花股份', '2024FY', 2024, 80000000, 40000000, 500000000),
        (6, '600085', '同仁堂', '2023FY', 2023, 700000000, 400000000, 2800000000),
        (7, '600085', '同仁堂', '2024FY', 2024, 900000000, 500000000, 3000000000),
        (8, '600557', '康缘药业', '2023FY', 2023, 150000000, 80000000, 700000000),
        (9, '600557', '康缘药业', '2024FY', 2024, 200000000, 100000000, 800000000),
    ]
    conn.executemany(
        "INSERT INTO income_sheet (serial_number, stock_code, stock_abbr, report_period, report_year, total_profit, net_profit, total_operating_revenue) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
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
        rows_hint="结果共 1 行，已完整展示。",
    )
    reflect_content = load_prompt(
        "reflect.md",
        question="金花股份2025年第三季度利润总额是多少",
        intent_json='{"tables": ["income_sheet"], "fields": ["total_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": false}',
        sql="SELECT total_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3'",
        rows_json='[{"total_profit": 123}]',
        rows_hint="结果共 1 行，已完整展示。",
    )
    assert "金花股份2025年第三季度利润总额是多少" in validate_content
    assert "金花股份2025年第三季度利润总额是多少" in reflect_content


def test_second_layer_result_validation_regenerates_sql(tmp_path: Path):
    class StubLLM:
        def __init__(self):
            self.calls = []
            self.validation_count = 0

        def complete(self, prompt: str, **kwargs) -> str | dict:
            self.calls.append((prompt, kwargs))
            if "提取结构化查询意图" in prompt:
                return {"tables": ["income_sheet"], "fields": ["total_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": False}
            if "生成单条 SQL" in prompt:
                if "补充约束" in prompt:
                    return "```sql\nSELECT total_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
                return "```sql\nSELECT net_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
            if "结果校验器" in prompt:
                self.validation_count += 1
                if self.validation_count == 1:
                    return {"accepted": False, "reason": "返回了净利润字段，不是利润总额字段。"}
                return {"accepted": True, "reason": ""}
            if "任务反思器" in prompt:
                return {"accepted": True, "reason": "", "rewritten_question": ""}
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

        def complete(self, prompt: str, **kwargs) -> str | dict:
            if "提取结构化查询意图" in prompt:
                return {"tables": ["income_sheet"], "fields": ["total_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": False}
            if "生成单条 SQL" in prompt:
                return "```sql\nSELECT net_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
            if "结果校验器" in prompt:
                self.validation_count += 1
                return {"accepted": False, "reason": "仍然返回了错误字段。"}
            if "任务反思器" in prompt:
                raise AssertionError("validation should fail before reflection")
            raise AssertionError(prompt)

    engine = Text2SQLEngine(make_db(tmp_path), llm_client=StubLLM())
    result = engine.query("金花股份2025年第三季度利润总额是多少")
    assert result.error is None
    assert result.warning == "仍然返回了错误字段。"
    assert result.rows[0]["net_profit"] == 31400000


def test_second_layer_result_validation_returns_warning_when_rows_exist(tmp_path: Path):
    class StubLLM:
        def __init__(self):
            self.validation_count = 0

        def complete(self, prompt: str, **kwargs) -> str | dict:
            if "提取结构化查询意图" in prompt:
                return {"tables": ["income_sheet"], "fields": ["total_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": False}
            if "生成单条 SQL" in prompt:
                return "```sql\nSELECT net_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
            if "结果校验器" in prompt:
                self.validation_count += 1
                return {"accepted": False, "reason": "仅查到部分指标。"}
            if "任务反思器" in prompt:
                return {"accepted": True, "reason": "", "rewritten_question": ""}
            raise AssertionError(prompt)

    engine = Text2SQLEngine(make_db(tmp_path), llm_client=StubLLM())
    result = engine.query("金花股份2025年第三季度利润总额是多少")
    assert result.error is None
    assert result.warning == "仅查到部分指标。"
    assert result.rows[0]["net_profit"] == 31400000


def test_third_layer_reflection_reanalyzes_intent(tmp_path: Path):
    class StubLLM:
        def __init__(self):
            self.reflect_count = 0

        def complete(self, prompt: str, **kwargs) -> str | dict:
            if "提取结构化查询意图" in prompt:
                if "请查询金花股份2025年第三季度利润总额" in prompt:
                    return {"tables": ["income_sheet"], "fields": ["total_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": False}
                return {"tables": ["income_sheet"], "fields": ["net_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": False}
            if "生成单条 SQL" in prompt:
                if '"total_profit"' in prompt:
                    return "```sql\nSELECT total_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
                return "```sql\nSELECT net_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
            if "结果校验器" in prompt:
                return {"accepted": True, "reason": ""}
            if "任务反思器" in prompt:
                self.reflect_count += 1
                if self.reflect_count == 1:
                    return {"accepted": False, "reason": "原始任务要查询利润总额，不是净利润。", "rewritten_question": "请查询金花股份2025年第三季度利润总额"}
                return {"accepted": True, "reason": "", "rewritten_question": ""}
            raise AssertionError(prompt)

    engine = Text2SQLEngine(make_db(tmp_path), llm_client=StubLLM())
    result = engine.query("金花股份2025年第三季度盈利情况")
    assert result.error is None
    assert result.sql and "total_profit" in result.sql
    assert result.rows[0]["total_profit"] == 123000000
    assert result.intent["fields"] == ["total_profit"]


def test_third_layer_reflection_reanalysis_keeps_conversation_context(tmp_path: Path):
    """Verify that _query_with_recovery passes conversation to analyze during reflection."""
    analyze_calls = []

    class StubLLM:
        def __init__(self):
            self.reflect_count = 0

        def complete(self, prompt: str, **kwargs) -> str | dict:
            if "提取结构化查询意图" in prompt:
                analyze_calls.append(prompt)
                return {"tables": ["income_sheet"], "fields": ["total_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": False}
            if "生成单条 SQL" in prompt:
                return "```sql\nSELECT total_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
            if "结果校验器" in prompt:
                return {"accepted": True, "reason": ""}
            if "任务反思器" in prompt:
                self.reflect_count += 1
                if self.reflect_count == 1:
                    return {"accepted": False, "reason": "需要重新分析", "rewritten_question": "请查询金花股份2025年第三季度利润总额"}
                return {"accepted": True, "reason": "", "rewritten_question": ""}
            raise AssertionError(prompt)

    engine = Text2SQLEngine(make_db(tmp_path), llm_client=StubLLM())
    conv = ConversationManager()
    conv.add_user_message("金花股份利润总额是多少")
    conv.slots["companies"] = ["金花股份"]

    result = engine.query("金花股份2025年第三季度利润总额", conv)
    assert result.error is None
    assert result.sql and "total_profit" in result.sql
    # Reflection triggers re-analysis: there should be 2 analyze calls
    assert len(analyze_calls) == 2
    # Second analyze call (reflection) should include conversation text
    assert "金花股份利润总额是多少" in analyze_calls[1]


def test_third_layer_reflection_stops_after_one_retry(tmp_path: Path):
    class StubLLM:
        def __init__(self):
            self.reflect_count = 0

        def complete(self, prompt: str, **kwargs) -> str | dict:
            if "提取结构化查询意图" in prompt:
                return {"tables": ["income_sheet"], "fields": ["net_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": False}
            if "生成单条 SQL" in prompt:
                return "```sql\nSELECT net_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
            if "结果校验器" in prompt:
                return {"accepted": True, "reason": ""}
            if "任务反思器" in prompt:
                self.reflect_count += 1
                return {"accepted": False, "reason": "任务理解仍然错误。", "rewritten_question": "请查询金花股份2025年第三季度利润总额"}
            raise AssertionError(prompt)

    engine = Text2SQLEngine(make_db(tmp_path), llm_client=StubLLM())
    result = engine.query("金花股份2025年第三季度盈利情况")
    assert result.error is None
    assert result.warning == "任务理解仍然错误。"
    assert result.rows[0]["net_profit"] == 31400000


def test_third_layer_reflection_returns_warning_when_rows_exist(tmp_path: Path):
    class StubLLM:
        def __init__(self):
            self.reflect_count = 0

        def complete(self, prompt: str, **kwargs) -> str | dict:
            if "提取结构化查询意图" in prompt:
                return {"tables": ["income_sheet"], "fields": ["net_profit"], "companies": ["金花股份"], "periods": ["2025Q3"], "is_trend": False}
            if "生成单条 SQL" in prompt:
                return "```sql\nSELECT net_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';\n```"
            if "结果校验器" in prompt:
                return {"accepted": True, "reason": ""}
            if "任务反思器" in prompt:
                self.reflect_count += 1
                return {"accepted": False, "reason": "只查到部分年份数据。", "rewritten_question": "请查询金花股份2025年第三季度利润总额"}
            raise AssertionError(prompt)

    engine = Text2SQLEngine(make_db(tmp_path), llm_client=StubLLM())
    result = engine.query("金花股份2025年第三季度盈利情况")
    assert result.error is None
    assert result.warning == "只查到部分年份数据。"
    assert result.rows[0]["net_profit"] == 31400000


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

    sql, rows, final_intent, warning = engine._query_with_recovery("金花股份2025年第三季度利润总额是多少", intent)

    assert sql and "total_profit" in sql
    assert rows[0]["total_profit"] == 123000000
    assert warning is None
    assert intent == snapshot
    assert final_intent == snapshot


def test_prompt_row_truncation_for_validation_and_reflection(tmp_path: Path):
    captured_prompts = []

    class StubLLM:
        def complete(self, prompt: str, **kwargs) -> dict:
            captured_prompts.append((prompt, kwargs))
            if "结果校验器" in prompt:
                return {"accepted": True, "reason": ""}
            if "任务反思器" in prompt:
                return {"accepted": True, "reason": "", "rewritten_question": ""}
            raise AssertionError(prompt)

    engine = Text2SQLEngine(make_db(tmp_path), llm_client=StubLLM())
    rows = [{"idx": i} for i in range(MAX_PROMPT_ROWS + 5)]
    engine._validate_result("q", {}, "SELECT 1", rows)
    engine._reflect_task("q", {}, "SELECT 1", rows)

    assert len(captured_prompts) == 2
    for prompt, kwargs in captured_prompts:
        assert kwargs.get("json_mode") is True
        assert f"结果已截断，共 {MAX_PROMPT_ROWS + 5} 行" in prompt
        assert '"idx": 49' in prompt
        assert '"idx": 50' not in prompt


def test_llm_client_complete_wraps_prompt_messages():
    captured = {}

    class StubCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            class Message:
                content = "ok"
            class Choice:
                message = Message()
            class Response:
                choices = [Choice()]
            return Response()

    class StubChat:
        completions = StubCompletions()

    class StubOpenAI:
        chat = StubChat()

    client = LLMClient(client=StubOpenAI(), model="demo", timeout=30)
    result = client.complete("hello", temperature=0.2)

    assert result == "ok"
    assert captured["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["temperature"] == 0.2


def test_recent_n_years_resolves_from_db_max_year(tmp_path: Path):
    """'近三年' should resolve to 2022FY/2023FY/2024FY based on DB max year (2024)."""
    engine = Text2SQLEngine(make_multi_year_db(tmp_path))
    intent = engine.analyze("华润三九近三年净利润趋势")
    assert intent["periods"] == ["2022FY", "2023FY", "2024FY"]
    assert intent["is_trend"] is True
    assert "华润三九" in intent["companies"]
    # Should generate valid SQL with IN clause
    sql = engine.generate_sql("华润三九近三年净利润趋势", intent)
    assert "IN" in sql
    assert "'2022FY'" in sql
    assert "'2024FY'" in sql


def test_top_n_generates_order_by_limit_sql(tmp_path: Path):
    """Top N query should generate ORDER BY + LIMIT without company filter."""
    engine = Text2SQLEngine(make_multi_year_db(tmp_path))
    intent = engine.analyze("2024年利润总额最高的top3企业")
    assert intent["top_n"] == 3
    assert intent["order_direction"] == "DESC"
    assert intent["companies"] == []
    sql = engine.generate_sql("2024年利润总额最高的top3企业", intent)
    assert "ORDER BY" in sql
    assert "LIMIT 3" in sql
    assert "stock_abbr" in sql
    result = engine.query("2024年利润总额最高的top3企业")
    assert result.error is None
    assert len(result.rows) == 3
    assert result.rows[0]["stock_abbr"] == "同仁堂"
    assert result.rows[1]["stock_abbr"] == "华润三九"
    assert result.rows[2]["stock_abbr"] == "康缘药业"


def test_yoy_intent_and_sql_generation(tmp_path: Path):
    engine = Text2SQLEngine(make_multi_year_db(tmp_path))
    intent = engine.analyze("华润三九2024年净利润同比")
    assert intent["yoy"] is True
    assert intent["fields"] == ["net_profit"]
    assert intent["periods"] == ["2024FY"]
    sql = engine.generate_sql("华润三九2024年净利润同比", intent)
    assert "JOIN income_sheet b ON a.stock_abbr = b.stock_abbr" in sql
    assert "b.report_period = '2023FY'" in sql
    assert "CASE WHEN b.net_profit = 0 THEN NULL ELSE ROUND((a.net_profit - b.net_profit) * 1.0 / b.net_profit, 4) END AS yoy_ratio" in sql
    result = engine.query("华润三九2024年净利润同比")
    assert result.error is None
    assert result.rows[0]["stock_abbr"] == "华润三九"
    assert result.rows[0]["current_value"] == 400000000
    assert result.rows[0]["previous_value"] == 350000000
    assert result.rows[0]["yoy_ratio"] == 0.1429


def test_list_companies_handles_missing_tables(tmp_path: Path):
    db_path = tmp_path / "partial.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE income_sheet (stock_abbr TEXT)")
    conn.execute("INSERT INTO income_sheet (stock_abbr) VALUES ('华润三九')")
    conn.commit()
    conn.close()

    engine = Text2SQLEngine(str(db_path))
    assert engine.list_companies() == []


def test_yoy_zero_previous_value_returns_warning(tmp_path: Path):
    db_path = tmp_path / "finance_yoy_zero.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(CREATE_TABLE_SQL)
    conn.executemany(
        "INSERT INTO income_sheet (serial_number, stock_code, stock_abbr, report_period, report_year, total_profit, net_profit, total_operating_revenue) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, '000999', '华润三九', '2023FY', 2023, 600000000, 0, 2200000000),
            (2, '000999', '华润三九', '2024FY', 2024, 700000000, 400000000, 2500000000),
        ],
    )
    conn.commit()
    conn.close()

    engine = Text2SQLEngine(str(db_path))
    result = engine.query("华润三九2024年净利润同比")
    assert result.error is None
    assert result.warning == "上年同期值为零，无法计算同比增长率"
    assert result.rows[0]["yoy_ratio"] is None


def test_yoy_top_n_supports_multiple_companies(tmp_path: Path):
    engine = Text2SQLEngine(make_multi_year_db(tmp_path))
    intent = engine.analyze("2024年净利润同比增长最高的top2企业")
    assert intent["yoy"] is True
    assert intent["top_n"] == 2
    sql = engine.generate_sql("2024年净利润同比增长最高的top2企业", intent)
    assert "ORDER BY yoy_ratio DESC LIMIT 2" in sql
    result = engine.query("2024年净利润同比增长最高的top2企业")
    assert result.error is None
    assert len(result.rows) == 2
    assert result.rows[0]["stock_abbr"] == "金花股份"
    assert result.rows[0]["yoy_ratio"] == 0.3333


def test_yoy_without_period_triggers_clarification(tmp_path: Path):
    engine = Text2SQLEngine(make_multi_year_db(tmp_path))
    result = engine.query("华润三九营业收入同比是多少")
    assert result.needs_clarification is True
    assert "报告期" in (result.clarification_question or "")


def test_build_yoy_sql_raises_user_facing_error_for_empty_fields(tmp_path: Path):
    engine = Text2SQLEngine(make_multi_year_db(tmp_path))
    try:
        engine._build_yoy_sql("income_sheet", [], {"periods": ["2024FY"]})
    except UserFacingError as exc:
        assert "指标字段" in str(exc)
    else:
        raise AssertionError("expected UserFacingError for empty fields")


def test_yoy_fallback_when_previous_period_missing(tmp_path: Path):
    db_path = tmp_path / "finance_yoy_fallback.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(CREATE_TABLE_SQL)
    conn.execute(
        "INSERT INTO income_sheet (serial_number, stock_code, stock_abbr, report_period, report_year, total_profit, net_profit, total_operating_revenue) VALUES (1, '000999', '华润三九', '2024FY', 2024, 700000000, 400000000, 2500000000)"
    )
    conn.commit()
    conn.close()
    engine = Text2SQLEngine(str(db_path))
    result = engine.query("华润三九2024年净利润同比")
    assert result.error is None
    assert result.warning == "上年同期数据不存在，无法计算同比"
    assert result.intent.get("yoy_fallback") is True
    assert result.rows[0]["stock_abbr"] == "华润三九"
    assert result.rows[0]["net_profit"] == 400000000
