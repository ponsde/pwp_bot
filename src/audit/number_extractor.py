"""Extract numeric tokens from Chinese financial text.

A NumToken carries both the raw value and (when possible) a normalized amount
in 元 so downstream consistency checks can compare across mixed units.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


_UNIT_TO_YUAN = {
    "亿": 1e8,
    "亿元": 1e8,
    "万": 1e4,
    "万元": 1e4,
    "元": 1.0,
}

_PATTERN = re.compile(
    r"(?<![\w\d])"
    # Prefer comma-separated (1,234,567.89) first, then plain (3140 / 181.49).
    # Plain alternative uses \d+ not \d{1,3} so "2025" captures fully.
    r"(-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)"
    r"\s*"
    r"(亿元|亿|万元|万|元|%)?"
)


@dataclass(frozen=True)
class NumToken:
    value: float
    unit: str
    value_in_yuan: float | None


def extract_numbers(text: str) -> list[NumToken]:
    if not text:
        return []
    out: list[NumToken] = []
    for m in _PATTERN.finditer(text):
        raw, unit = m.group(1), (m.group(2) or "")
        try:
            val = float(raw.replace(",", ""))
        except ValueError:
            continue
        if not unit and raw.isdigit() and 1900 <= val <= 2100:
            continue
        if unit == "%":
            yuan = None
        elif unit in _UNIT_TO_YUAN:
            yuan = val * _UNIT_TO_YUAN[unit]
        else:
            yuan = None
        out.append(NumToken(value=val, unit=unit, value_in_yuan=yuan))
    return out
