"""Render Finding lists to human-readable Markdown for paper/audit_report.md."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from src.audit.checks import Finding


_HEADERS = {"blocking": "## 阻塞", "suspect": "## 可疑", "hint": "## 提示"}


def render_report(findings: Iterable[Finding], *, totals: dict[str, int]) -> str:
    by_sev: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_sev[f.severity].append(f)

    lines: list[str] = []
    lines.append("# 结果审计报告")
    lines.append("")
    summary = (
        f"阻塞 **{totals.get('blocking', 0)}**　"
        f"可疑 **{totals.get('suspect', 0)}**　"
        f"提示 **{totals.get('hint', 0)}**"
    )
    lines.append(summary)
    lines.append("")
    if sum(totals.values()) == 0:
        lines.append("全部通过，无发现。")
        return "\n".join(lines)

    for sev in ("blocking", "suspect", "hint"):
        items = by_sev.get(sev, [])
        if not items:
            continue
        lines.append(_HEADERS[sev])
        lines.append("")
        lines.append("| 题号 | 类别 | 说明 |")
        lines.append("| :-- | :-- | :-- |")
        for f in sorted(items, key=lambda x: x.row_id):
            detail = f.detail.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {f.row_id} | {f.kind} | {detail} |")
        lines.append("")
    return "\n".join(lines)
