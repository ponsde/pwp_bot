"""Conversation helpers for multi-turn financial QA."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List


@dataclass
class ConversationTurn:
    role: str
    content: str


@dataclass
class ConversationManager:
    history: List[ConversationTurn] = field(default_factory=list)
    slots: dict = field(default_factory=lambda: {
        "companies": [],
        "fields": [],
        "periods": [],
        "tables": [],
        "top_n": None,
        "order_direction": None,
    })

    def add_user_message(self, content: str) -> None:
        self.history.append(ConversationTurn(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        self.history.append(ConversationTurn(role="assistant", content=content))

    def extend(self, turns: Iterable[ConversationTurn]) -> None:
        self.history.extend(turns)

    def render(self) -> str:
        return "\n".join(f"{turn.role}: {turn.content}" for turn in self.history)

    def merge_intent(self, intent: dict) -> dict:
        merged = dict(intent)
        for key in ["tables", "fields", "companies", "periods"]:
            current = list(intent.get(key, []) or [])
            if current:
                self.slots[key] = current
                merged[key] = current
            else:
                merged[key] = list(self.slots.get(key, []))
        # top_n / order_direction persist across turns: user rarely restates
        # "top 5" when merely swapping periods ("那 2024Q3 的呢").
        for key in ["top_n", "order_direction"]:
            current = intent.get(key)
            if current:
                self.slots[key] = current
                merged[key] = current
            elif self.slots.get(key):
                merged[key] = self.slots[key]
        merged["is_trend"] = bool(intent.get("is_trend", False))
        merged["yoy"] = bool(intent.get("yoy", False))
        return merged

    def missing_slots(self, intent: dict) -> list[str]:
        missing: list[str] = []
        if not intent.get("companies") and not intent.get("top_n"):
            missing.append("公司名称")
        if not intent.get("fields"):
            missing.append("指标名称")
        # periods not required for trend queries (they query multiple periods)
        if not intent.get("periods") and not intent.get("is_trend"):
            missing.append("报告期")
        return missing

    def needs_clarification(self, intent: dict) -> bool:
        return bool(self.missing_slots(intent))
