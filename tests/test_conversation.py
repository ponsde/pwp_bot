from src.query.conversation import ConversationManager


def test_conversation_detects_missing_slots():
    manager = ConversationManager()
    missing = manager.missing_slots({"companies": [], "fields": ["total_profit"], "periods": []})
    assert missing == ["公司名称", "报告期"]


def test_top_n_skips_company_requirement():
    manager = ConversationManager()
    missing = manager.missing_slots({"companies": [], "fields": ["total_profit"], "periods": ["2024FY"], "top_n": 10})
    assert missing == []
