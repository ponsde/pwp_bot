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


_NUM_TOL_PASS = 0.01   # <=1% considered a pass (rounding / unit noise)
_NUM_TOL_SOFT = 0.15   # 1–15% → suspect (possible derived/rounded value)
# The ETL stores some columns in 万元, others in 元, and some derived ratios
# in raw float. When comparing a content number to SQL output, try every
# plausible scale: as-is, ×1e4 (万元→元), ×1e8 (亿元→元), and ÷1e4 in case
# the extractor flipped. This turns an ambiguous unit mismatch into a pass
# instead of a blocking finding.
_SCALE_FACTORS = (1.0, 1e4, 1e8, 1e-4)


def _sql_numeric_values(sql_rows: list[dict]) -> list[float]:
    out: list[float] = []
    for row in sql_rows:
        for v in row.values():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append(float(v))
    return out


_PAIRWISE_CAP = 50  # skip the O(n²) expansion when too many SQL values


def _candidate_values(sql_vals: list[float]) -> list[float]:
    """Direct SQL values + pairwise sums/differences.

    Content narratives frequently cite derived quantities: "same-period
    growth 约 1.13 亿元" is SQL_a − SQL_b, for example. Without this
    expansion we'd flag those as blocking. The O(n²) step is skipped for
    very long result sets (e.g., a SELECT returning every company's
    column) — at that size the direct match covers nearly all cases.
    """
    out: list[float] = list(sql_vals)
    n = len(sql_vals)
    if n > _PAIRWISE_CAP:
        return out
    for i in range(n):
        for j in range(i + 1, n):
            a, b = sql_vals[i], sql_vals[j]
            out.append(a + b)
            out.append(a - b)
            out.append(b - a)
    return out


def _best_rel_diff(target: float, candidates: list[float]) -> float | None:
    best: float | None = None
    for v in candidates:
        for scale in _SCALE_FACTORS:
            scaled = v * scale
            rel = abs(target - scaled) / max(abs(scaled), 1.0)
            if best is None or rel < best:
                best = rel
    return best


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
    candidates = _candidate_values(sql_vals)
    findings: list[Finding] = []
    for t in toks:
        best = _best_rel_diff(t.value_in_yuan, candidates)
        if best is None:
            continue
        if best <= _NUM_TOL_PASS:
            continue
        severity: Severity = "suspect" if best <= _NUM_TOL_SOFT else "blocking"
        findings.append(
            Finding(
                row_id=row_id,
                severity=severity,
                kind="num_mismatch",
                detail=(
                    f"content has {t.value}{t.unit} (≈{t.value_in_yuan:.2f} 元); "
                    f"closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) "
                    f"is off by {best*100:.2f}%"
                ),
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
