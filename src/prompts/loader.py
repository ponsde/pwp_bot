"""Prompt template loading utilities."""
from __future__ import annotations

from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).resolve().parent


class PromptTemplateError(ValueError):
    """Raised when a prompt template cannot be loaded or rendered."""


def load_prompt(template_name: str, **variables: Any) -> str:
    """Load a markdown prompt template and render it with variables.

    Uses Python's ``str.format`` semantics so templates can reference values as
    ``{variable}``.
    """

    path = PROMPTS_DIR / template_name
    if not path.exists():
        raise PromptTemplateError(f"Prompt template not found: {template_name}")

    content = path.read_text(encoding="utf-8")
    try:
        return content.format(**variables)
    except KeyError as exc:
        missing = exc.args[0]
        raise PromptTemplateError(
            f"Missing prompt variable '{missing}' for template {template_name}"
        ) from exc
