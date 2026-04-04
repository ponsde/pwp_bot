"""Shared query-layer constants."""
from __future__ import annotations

USER_VISIBLE_WARNING_WHITELIST: tuple[str, ...] = (
    "上年同期值为零，无法计算同比增长率",
    "上年同期数据不存在，无法计算同比",
)
