from src.audit.llm_judge import judge_narrative, JudgeVerdict


class _StubLLM:
    def __init__(self, reply: str):
        self._reply = reply

    def complete(self, prompt: str, **_) -> str:
        return self._reply


def test_judge_parses_well_formed_reply():
    reply = '{"score": 3, "reason": "切题且引用充分"}'
    v = judge_narrative(
        question="主营业务收入上升的原因是什么",
        content="因大健康业务扩张与海外市场拓展",
        references_text=["大健康业务 2024 年增长 30%"],
        llm=_StubLLM(reply),
    )
    assert v.score == 3
    assert "切题" in v.reason


def test_judge_low_score_flags_blocking():
    reply = '{"score": 0, "reason": "幻觉明显"}'
    v = judge_narrative(
        question="xxx", content="yyy", references_text=[], llm=_StubLLM(reply)
    )
    assert v.score == 0
    assert v.is_weak() is True


def test_judge_degraded_on_garbage_reply_returns_unknown():
    v = judge_narrative(
        question="xxx",
        content="yyy",
        references_text=[],
        llm=_StubLLM("not json at all"),
    )
    assert v.score is None
    assert v.is_weak() is False


def test_judge_none_llm_returns_unknown():
    v = judge_narrative(
        question="x", content="y", references_text=[], llm=None
    )
    assert v.score is None
