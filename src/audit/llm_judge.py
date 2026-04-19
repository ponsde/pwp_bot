"""LLM-as-judge narrative scoring for Hybrid / multi-intent task-3 rows.

The LLM is asked to return strict JSON ``{"score": 0-3, "reason": "..."}``.
Failures (garbage output, no LLM, transport error) degrade to score=None so
the caller can treat "unknown" differently from "weak".
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol


class _LLM(Protocol):
    def complete(self, prompt: str, **kw) -> str: ...


_PROMPT = (
    "你是财务问答答案质量评审员。读一道题和助手给的 content，给 0-3 分：\n"
    "3=切题且数据/引用充分；2=切题但细节薄弱；1=偏题或仅套话；0=有幻觉/答非所问。\n"
    "只返回 JSON：{{\"score\": 0-3, \"reason\": \"一句话理由\"}}。\n\n"
    "问题：{q}\n"
    "content：{c}\n"
    "references text：{r}\n"
)


@dataclass(frozen=True)
class JudgeVerdict:
    score: int | None
    reason: str

    def is_weak(self) -> bool:
        return self.score is not None and self.score <= 1


def judge_narrative(
    *, question: str, content: str, references_text: list[str], llm: _LLM | None
) -> JudgeVerdict:
    if llm is None:
        return JudgeVerdict(score=None, reason="no_llm")
    prompt = _PROMPT.format(
        q=question[:500],
        c=content[:1500],
        r=" / ".join(references_text)[:1500] or "（无）",
    )
    try:
        reply = str(llm.complete(prompt))
    except Exception as exc:  # noqa: BLE001
        return JudgeVerdict(score=None, reason=f"llm_error:{exc}")

    m = re.search(r"\{[^{}]*\}", reply, re.DOTALL)
    if not m:
        return JudgeVerdict(score=None, reason="no_json")
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return JudgeVerdict(score=None, reason="bad_json")
    score = data.get("score")
    if not isinstance(score, int) or not (0 <= score <= 3):
        return JudgeVerdict(score=None, reason="bad_score")
    return JudgeVerdict(score=score, reason=str(data.get("reason") or ""))
