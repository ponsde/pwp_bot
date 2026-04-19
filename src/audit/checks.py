"""Pure check functions. Each returns a list[Finding]; empty == pass."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.audit.number_extractor import extract_numbers


Severity = Literal["blocking", "suspect", "hint"]


@dataclass(frozen=True)
class Finding:
    row_id: str
    severity: Severity
    kind: str
    detail: str


_NUM_TOL = 0.01


def _sql_numeric_values(sql_rows: list[dict]) -> list[float]:
    out: list[float] = []
    for row in sql_rows:
        for v in row.values():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append(float(v))
    return out


def check_number_consistency(
    row_id: str, *, content: str, sql_rows: list[dict]
) -> list[Finding]:
    if not sql_rows:
        return []
    toks = [t for t in extract_numbers(content) if t.value_in_yuan is not None]
    if not toks:
        return []
    sql_vals = _sql_numeric_values(sql_rows)
    if not sql_vals:
        return []
    findings: list[Finding] = []
    for t in toks:
        best = min(
            (abs(t.value_in_yuan - v) / max(abs(v), 1.0) for v in sql_vals),
            default=None,
        )
        if best is None or best > _NUM_TOL:
            findings.append(
                Finding(
                    row_id=row_id,
                    severity="blocking",
                    kind="num_mismatch",
                    detail=f"content has {t.value}{t.unit} (={t.value_in_yuan:.2f} 元), no SQL value within 1%",
                )
            )
    return findings


def check_chart_file(row_id: str, *, path: Path) -> list[Finding]:
    if not path.exists():
        return [
            Finding(
                row_id=row_id,
                severity="blocking",
                kind="chart_missing",
                detail=f"expected chart at {path} but file not found",
            )
        ]
    if path.stat().st_size == 0:
        return [
            Finding(
                row_id=row_id,
                severity="blocking",
                kind="chart_zero_bytes",
                detail=f"chart at {path} is 0 bytes",
            )
        ]
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return []
    try:
        with Image.open(path) as im:
            w, h = im.size
        if w < 400 or h < 300:
            return [
                Finding(
                    row_id=row_id,
                    severity="suspect",
                    kind="chart_too_small",
                    detail=f"chart at {path} is only {w}x{h}",
                )
            ]
    except Exception as exc:
        return [
            Finding(
                row_id=row_id,
                severity="suspect",
                kind="chart_unreadable",
                detail=f"PIL failed to open {path}: {exc}",
            )
        ]
    return []
