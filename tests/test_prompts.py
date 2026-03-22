from src.prompts.loader import load_prompt


def test_load_prompt_renders_variables():
    content = load_prompt("clarify.md", question="利润总额是多少", missing_info="报告期", conversation="")
    assert "利润总额是多少" in content
    assert "报告期" in content
