import json

from scripts.fix_audit_findings import rewrite_content_in_cell


class _StubLLM:
    def complete(self, prompt: str, **_) -> str:
        return "重写后的 content：利润总额是 3140 万元。"


def test_rewrite_replaces_only_weak_content():
    cell = json.dumps(
        [{"Q": "利润", "A": {"content": "xyz", "references": []}}],
        ensure_ascii=False,
    )
    out = rewrite_content_in_cell(
        cell,
        sql_rows=[{"total_profit": 31_400_000.0}],
        llm=_StubLLM(),
        weak_ids={0},
    )
    data = json.loads(out)
    assert "3140" in data[0]["A"]["content"]


def test_rewrite_keeps_unflagged_turns():
    cell = json.dumps(
        [
            {"Q": "a", "A": {"content": "keep me", "references": []}},
            {"Q": "b", "A": {"content": "rewrite me", "references": []}},
        ],
        ensure_ascii=False,
    )
    out = rewrite_content_in_cell(
        cell, sql_rows=[], llm=_StubLLM(), weak_ids={1},
    )
    data = json.loads(out)
    assert data[0]["A"]["content"] == "keep me"
    assert "重写后" in data[1]["A"]["content"]
