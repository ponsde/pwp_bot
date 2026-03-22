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

    def add_user_message(self, content: str) -> None:
        self.history.append(ConversationTurn(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        self.history.append(ConversationTurn(role="assistant", content=content))

    def extend(self, turns: Iterable[ConversationTurn]) -> None:
        self.history.extend(turns)

    def render(self) -> str:
        return "\n".join(f"{turn.role}: {turn.content}" for turn in self.history)

    def missing_slots(self, intent: dict) -> list[str]:
        missing: list[str] = []
        if not intent.get("companies"):
            missing.append("公司名称")
        if not intent.get("fields"):
            missing.append("指标名称")
        if not intent.get("periods"):
            missing.append("报告期")
        return missing

    def needs_clarification(self, intent: dict) -> bool:
        return bool(self.missing_slots(intent))
