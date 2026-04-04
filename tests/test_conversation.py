from src.query.conversation import ConversationManager


def test_conversation_detects_missing_slots():
    manager = ConversationManager()
    missing = manager.missing_slots({"companies": [], "fields": ["total_profit"], "periods": []})
    assert missing == ["公司名称", "报告期"]


def test_top_n_skips_company_requirement():
    manager = ConversationManager()
    missing = manager.missing_slots({"companies": [], "fields": ["total_profit"], "periods": ["2024FY"], "top_n": 10})
    assert missing == []


def test_merge_intent_keeps_yoy_per_turn():
    manager = ConversationManager()
    merged = manager.merge_intent({
        "tables": ["income_sheet"],
        "fields": ["net_profit"],
        "companies": ["华润三九"],
        "periods": ["2024FY"],
        "yoy": True,
    })
    assert merged["yoy"] is True
    merged2 = manager.merge_intent({"tables": [], "fields": [], "companies": [], "periods": []})
    assert merged2["companies"] == ["华润三九"]
    assert merged2["periods"] == ["2024FY"]
    assert merged2["yoy"] is False
