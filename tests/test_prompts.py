from src.prompts.loader import load_prompt


def test_load_prompt_renders_variables():
    content = load_prompt("clarify.md", question="利润总额是多少", missing_info="报告期", conversation="")
    assert "利润总额是多少" in content
    assert "报告期" in content


def test_generate_sql_prompt_includes_calculation_examples():
    content = load_prompt(
        "generate_sql.md",
        schema_sql="schema",
        intent_json='{"tables": ["income_sheet"], "fields": ["net_profit", "total_operating_revenue"], "companies": ["华润三九"], "periods": ["2023FY"], "is_trend": false}',
        question="华润三九2023年净利润占营业收入的比例",
    )
    assert "net_profit * 1.0 / total_operating_revenue" in content
    assert "营业收入比2023年增长多少" in content


def test_seek_table_prompt_includes_calculation_examples():
    content = load_prompt(
        "seek_table.md",
        field_catalog='{"income_sheet": ["net_profit", "total_operating_revenue"]}',
        conversation="",
        question="华润三九2023年净利润占营业收入的比例",
    )
    assert '"fields":["net_profit","total_operating_revenue"]' in content
    assert "总资产减总负债" in content
