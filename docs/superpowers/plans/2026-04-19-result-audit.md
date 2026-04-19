# Result Audit + Fix Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a reproducible audit + fix pipeline that reduces `result_2.xlsx` / `result_3.xlsx` / `result/*.jpg` mechanical errors to zero and flags suspect LLM narrative before 2026-04-24 submission.

**Architecture:** A `src/audit/` package exposes pure check functions (number consistency, chart file sanity, reference validity, LLM-as-judge narrative scoring) composed by a `scripts/audit_results.py` CLI that emits a tri-severity `paper/audit_report.md`. A companion `scripts/fix_audit_findings.py` reads that report and applies three action kinds: `clean_refs`, `rewrite_content`, `reanswer`. TDD throughout; all new logic lives behind unit tests with mocked LLM / filesystem boundaries.

**Tech Stack:** Python 3.12, pytest, openpyxl (xlsx), sqlite3 (already in finance.db), matplotlib (existing `src/query/chart.py`), OpenAI-compatible LLM client (existing `src/llm/client.py`).

---

## Spec reference

Design spec: `docs/superpowers/specs/2026-04-19-result-audit-design.md`.

## File structure

New files under `src/audit/`:

- `src/audit/__init__.py` — package marker, re-export public funcs.
- `src/audit/number_extractor.py` — extract numeric tokens (value + unit) from Chinese financial text.
- `src/audit/sql_runner.py` — execute a row's SQL from xlsx against the SQLite DB, return list[dict] rows.
- `src/audit/checks.py` — each check is a pure function `(AuditCtx) -> list[Finding]`. `Finding = {row_id, severity, kind, detail}`.
- `src/audit/reference_validator.py` — validate `references.paper_path` exists and `references.text` fragment-matches an OV resource chunk.
- `src/audit/llm_judge.py` — narrative scoring for Hybrid / multi-intent rows; LLM-backed with a stub path for tests.
- `src/audit/report.py` — serialize findings to Markdown grouped by severity.

New CLI scripts:

- `scripts/audit_results.py` — orchestrator. Flags: `--xlsx`, `--db`, `--task {2,3}`, `--out`.
- `scripts/fix_audit_findings.py` — applies fixes from report to xlsx and refs.

Modify:

- `scripts/regen_charts.py` — no structural change needed; the existing `--xlsx` loop already covers all chart rows. Task 14 only **runs** it against both files.

Tests (new `tests/audit/` subdir):

- `tests/audit/__init__.py`
- `tests/audit/test_number_extractor.py`
- `tests/audit/test_sql_runner.py`
- `tests/audit/test_checks.py`
- `tests/audit/test_reference_validator.py`
- `tests/audit/test_llm_judge.py`
- `tests/audit/test_report.py`
- `tests/audit/test_integration.py`

---

### Task 1: Scaffold audit package and test directory

**Files:**
- Create: `src/audit/__init__.py`
- Create: `tests/audit/__init__.py`

- [ ] **Step 1: Create empty package markers**

```python
# src/audit/__init__.py
"""Result quality audit module.

Exposes pure check functions used by scripts/audit_results.py. Every public
entrypoint takes plain dicts / paths so the check layer stays independent of
openpyxl, sqlite3, or the LLM client.
"""
```

```python
# tests/audit/__init__.py
```

- [ ] **Step 2: Verify pytest sees the new path**

Run: `.venv/bin/python -m pytest tests/audit/ -v`
Expected: `no tests ran` (exit 5). That is fine — the package is discoverable.

- [ ] **Step 3: Commit**

```bash
git add src/audit/__init__.py tests/audit/__init__.py
git commit -m "chore(audit): scaffold audit package and test dir"
```

---

### Task 2: Number extraction

**Files:**
- Create: `src/audit/number_extractor.py`
- Test: `tests/audit/test_number_extractor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/audit/test_number_extractor.py
from src.audit.number_extractor import extract_numbers, NumToken


def test_extract_simple_cn_amount():
    text = "金花股份 2025 年第三季度的利润总额是 3140 万元。"
    toks = extract_numbers(text)
    vals = [t.value_in_yuan for t in toks]
    assert 31_400_000.0 in vals


def test_extract_yi_unit():
    toks = extract_numbers("营业收入 181.49 亿元")
    assert toks and abs(toks[0].value_in_yuan - 18_149_000_000.0) < 1.0


def test_extract_percent_is_kept_separately():
    toks = extract_numbers("同比增长 18.85%")
    assert any(t.unit == "%" and abs(t.value - 18.85) < 1e-6 for t in toks)


def test_extract_ignores_year_like_numbers():
    toks = extract_numbers("2024 年")
    # Stand-alone year should not be extracted as a financial amount
    assert all(t.unit for t in toks)


def test_extract_handles_comma_separated():
    toks = extract_numbers("资产总计 1,234,567.89 元")
    assert any(abs(t.value_in_yuan - 1234567.89) < 1e-6 for t in toks)
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `.venv/bin/python -m pytest tests/audit/test_number_extractor.py -v`
Expected: ModuleNotFoundError for `src.audit.number_extractor`.

- [ ] **Step 3: Implement minimal extractor**

```python
# src/audit/number_extractor.py
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
    r"(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?)"
    r"\s*"
    r"(亿元|亿|万元|万|元|%)?"
)


@dataclass(frozen=True)
class NumToken:
    value: float
    unit: str  # "" if bare number
    value_in_yuan: float | None  # None if unit == "%"


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
        # Skip bare numbers that look like a year: 4-digit integer between
        # 1900 and 2100 with no unit and no decimal. Avoids matching "2025".
        if not unit and raw.isdigit() and 1900 <= val <= 2100:
            continue
        if unit == "%":
            yuan = None
        elif unit in _UNIT_TO_YUAN:
            yuan = val * _UNIT_TO_YUAN[unit]
        else:
            yuan = None  # bare number; can't compare meaningfully
        out.append(NumToken(value=val, unit=unit, value_in_yuan=yuan))
    return out
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/audit/test_number_extractor.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/audit/number_extractor.py tests/audit/test_number_extractor.py
git commit -m "feat(audit): extract numeric tokens from Chinese financial text"
```

---

### Task 3: SQL re-runner

**Files:**
- Create: `src/audit/sql_runner.py`
- Test: `tests/audit/test_sql_runner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/audit/test_sql_runner.py
import sqlite3
from pathlib import Path

import pytest

from src.audit.sql_runner import run_sql_strict, SqlRunError


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "t.db"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE x (a INTEGER, b TEXT)")
    con.execute("INSERT INTO x VALUES (1, 'foo')")
    con.execute("INSERT INTO x VALUES (2, 'bar')")
    con.commit()
    con.close()
    return db_path


def test_run_sql_returns_dicts(tmp_db: Path):
    rows = run_sql_strict(tmp_db, "SELECT a, b FROM x ORDER BY a")
    assert rows == [{"a": 1, "b": "foo"}, {"a": 2, "b": "bar"}]


def test_run_sql_raises_on_bad_sql(tmp_db: Path):
    with pytest.raises(SqlRunError):
        run_sql_strict(tmp_db, "SELECT * FROM does_not_exist")


def test_run_sql_empty_result_ok(tmp_db: Path):
    assert run_sql_strict(tmp_db, "SELECT a FROM x WHERE a = 99") == []


def test_run_sql_handles_none_or_empty_input(tmp_db: Path):
    assert run_sql_strict(tmp_db, "") == []
    assert run_sql_strict(tmp_db, "   ") == []
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `.venv/bin/python -m pytest tests/audit/test_sql_runner.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/audit/sql_runner.py
"""Execute a stored SQL string against the finance DB.

Wraps sqlite3 so the audit layer doesn't have to import it directly, and so
empty / whitespace SQL (which shows up as "无" for pure-RAG task-3 rows)
becomes a safe no-op instead of an exception.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


class SqlRunError(Exception):
    """Raised when a non-empty SQL string fails to execute."""


def run_sql_strict(db_path: Path | str, sql: str) -> list[dict]:
    if not sql or not sql.strip():
        return []
    con = sqlite3.connect(str(db_path))
    try:
        try:
            cur = con.execute(sql)
        except sqlite3.Error as exc:
            raise SqlRunError(str(exc)) from exc
        cols = [d[0] for d in (cur.description or [])]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        con.close()
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/audit/test_sql_runner.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/audit/sql_runner.py tests/audit/test_sql_runner.py
git commit -m "feat(audit): sql_runner wraps sqlite3 with empty-SQL safety"
```

---

### Task 4: Findings type + number consistency check

**Files:**
- Modify: `src/audit/__init__.py`
- Create: `src/audit/checks.py`
- Test: `tests/audit/test_checks.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/audit/test_checks.py
from pathlib import Path

import pytest

from src.audit.checks import (
    Finding,
    check_number_consistency,
    check_chart_file,
)


def test_finding_defaults():
    f = Finding(row_id="B1001", severity="blocking", kind="num_mismatch", detail="x")
    assert f.severity in {"blocking", "suspect", "hint"}


def test_number_consistency_passes_when_all_numbers_present():
    sql_rows = [{"total_profit": 31_400_000.0}]
    content = "金花股份 2025 年第三季度的利润总额是 3140 万元。"
    findings = check_number_consistency("B1001", content=content, sql_rows=sql_rows)
    assert findings == []


def test_number_consistency_flags_mismatch_over_threshold():
    sql_rows = [{"total_profit": 31_400_000.0}]
    content = "利润总额是 500 万元。"  # way off
    findings = check_number_consistency("B1001", content=content, sql_rows=sql_rows)
    assert findings and findings[0].severity == "blocking"
    assert "500" in findings[0].detail


def test_number_consistency_tolerates_rounding():
    sql_rows = [{"total_profit": 31_400_000.0}]
    content = "利润总额约 3141 万元。"  # 0.03% drift
    assert check_number_consistency("B1001", content=content, sql_rows=sql_rows) == []


def test_number_consistency_skips_when_no_sql():
    # Pure-RAG task-3 rows have no SQL; don't emit false positives.
    assert check_number_consistency("B2002", content="100 万元", sql_rows=[]) == []


def test_chart_file_missing(tmp_path: Path):
    findings = check_chart_file("B1002", path=tmp_path / "does_not_exist.jpg")
    assert findings and findings[0].severity == "blocking"


def test_chart_file_zero_bytes(tmp_path: Path):
    p = tmp_path / "empty.jpg"
    p.write_bytes(b"")
    findings = check_chart_file("B1002", path=p)
    assert findings and findings[0].severity == "blocking"


def test_chart_file_small_dimensions_flags_suspect(tmp_path: Path):
    # Fake a too-small image by writing a tiny JPEG.
    import struct
    p = tmp_path / "tiny.jpg"
    # Minimal JPEG (10x10) via Pillow if available, else skip this dim check.
    try:
        from PIL import Image
        Image.new("RGB", (10, 10), "white").save(p, "JPEG")
    except ImportError:
        pytest.skip("Pillow unavailable")
    findings = check_chart_file("B1002", path=p)
    assert any(f.severity == "suspect" for f in findings)
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `.venv/bin/python -m pytest tests/audit/test_checks.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/audit/checks.py
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


_NUM_TOL = 0.01  # 1% relative tolerance


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
    """Every value-in-元 token in content must be within 1% of some SQL value.

    Pure-RAG rows (sql_rows == []) are skipped — there's nothing to compare to.
    Percent-only tokens (unit == "%") are skipped for now; SQL result seldom
    carries % natively.
    """
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
    # Dimension check (requires Pillow; stay tolerant if it's unavailable)
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
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/audit/test_checks.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/audit/checks.py tests/audit/test_checks.py
git commit -m "feat(audit): number consistency and chart file checks"
```

---

### Task 5: Reference validator

**Files:**
- Create: `src/audit/reference_validator.py`
- Test: `tests/audit/test_reference_validator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/audit/test_reference_validator.py
from pathlib import Path

from src.audit.reference_validator import validate_reference, RefResult


def test_validate_reference_path_missing(tmp_path: Path):
    r = validate_reference(
        ref={"paper_path": str(tmp_path / "nope.pdf"), "text": "x"},
        repo_root=tmp_path,
        ov_root=tmp_path,
    )
    assert r.path_ok is False


def test_validate_reference_path_ok(tmp_path: Path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"fake")
    r = validate_reference(
        ref={"paper_path": str(p), "text": ""},
        repo_root=tmp_path,
        ov_root=tmp_path,
    )
    assert r.path_ok is True


def test_validate_reference_text_matches_resource_chunk(tmp_path: Path):
    ov_root = tmp_path / "viking" / "default" / "resources" / "myreport"
    ov_root.mkdir(parents=True)
    (ov_root / "myreport_1.md").write_text(
        "国家医保局 25 年 8 月公告初步审评的中成药共 23 种。", encoding="utf-8"
    )
    ref = {
        "paper_path": "./附件5：研报数据/行业研报/myreport.pdf",
        "text": "国家医保局 25 年 8 月公告初步审评",
    }
    r = validate_reference(
        ref=ref,
        repo_root=tmp_path,
        ov_root=ov_root.parents[2],
    )
    assert r.text_ok is True


def test_validate_reference_text_no_match(tmp_path: Path):
    ov_root = tmp_path / "viking" / "default" / "resources" / "myreport"
    ov_root.mkdir(parents=True)
    (ov_root / "myreport_1.md").write_text("完全不相关的内容", encoding="utf-8")
    ref = {
        "paper_path": "./附件5：研报数据/行业研报/myreport.pdf",
        "text": "国家医保局 25 年 8 月",
    }
    r = validate_reference(
        ref=ref,
        repo_root=tmp_path,
        ov_root=ov_root.parents[2],
    )
    assert r.text_ok is False


def test_validate_reference_ignores_viking_user_uri(tmp_path: Path):
    # viking://user/... and viking://session/... refs should be dropped
    # before this function is called, but verify it doesn't blow up.
    r = validate_reference(
        ref={"paper_path": "viking://user/foo", "text": ""},
        repo_root=tmp_path,
        ov_root=tmp_path,
    )
    assert r.path_ok is False
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `.venv/bin/python -m pytest tests/audit/test_reference_validator.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/audit/reference_validator.py
"""Validate a single reference dict extracted from result_3.xlsx 回答 JSON.

A reference is considered valid iff:
  1. paper_path points to a real file on disk (relative to repo_root).
  2. text is either empty OR has a >=5-consecutive-CJK-char match inside any
     .md chunk of the matching OV resource under ov_root/viking/default/resources/.

The resource name used for chunk lookup is sanitize(basename(paper_path)).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_SAN = re.compile(r"[^\w\u4e00-\u9fff]")
_MIN_MATCH_CHARS = 5


@dataclass(frozen=True)
class RefResult:
    path_ok: bool
    text_ok: bool


def _sanitize(stem: str) -> str:
    return _SAN.sub("", stem)


def validate_reference(
    *, ref: dict, repo_root: Path, ov_root: Path
) -> RefResult:
    paper_path = (ref.get("paper_path") or "").strip()
    text = (ref.get("text") or "").strip()

    # Path check
    path_ok = False
    if paper_path and not paper_path.startswith("viking://"):
        resolved = (repo_root / paper_path).resolve()
        path_ok = resolved.is_file()

    if not text:
        return RefResult(path_ok=path_ok, text_ok=True)

    # Text match: find candidate resource dir by sanitized stem of PDF name
    resources_root = ov_root / "viking" / "default" / "resources"
    if not resources_root.is_dir():
        return RefResult(path_ok=path_ok, text_ok=False)

    stem = Path(paper_path).stem
    key = _sanitize(stem)
    candidate_dirs = [d for d in resources_root.iterdir() if _sanitize(d.name) == key or d.name == stem]
    if not candidate_dirs:
        # fall back: scan every resource
        candidate_dirs = list(resources_root.iterdir())

    # Scan: take the first ≥5-char CJK/alnum slice of text and look it up in chunks.
    slice_probe = re.sub(r"\s+", "", text)
    if len(slice_probe) < _MIN_MATCH_CHARS:
        return RefResult(path_ok=path_ok, text_ok=True)  # too short to verify
    probe = slice_probe[:_MIN_MATCH_CHARS]

    for d in candidate_dirs:
        if not d.is_dir():
            continue
        for md in d.glob("*.md"):
            try:
                body = md.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if probe in re.sub(r"\s+", "", body):
                return RefResult(path_ok=path_ok, text_ok=True)
    return RefResult(path_ok=path_ok, text_ok=False)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/audit/test_reference_validator.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/audit/reference_validator.py tests/audit/test_reference_validator.py
git commit -m "feat(audit): validate reference path + text fragment against OV chunks"
```

---

### Task 6: LLM-as-judge narrative scoring

**Files:**
- Create: `src/audit/llm_judge.py`
- Test: `tests/audit/test_llm_judge.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/audit/test_llm_judge.py
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
        content="因大健康业务扩张与海外市场拓展…",
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
    assert v.is_weak() is False  # unknown != weak


def test_judge_none_llm_returns_unknown():
    v = judge_narrative(
        question="x", content="y", references_text=[], llm=None
    )
    assert v.score is None
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `.venv/bin/python -m pytest tests/audit/test_llm_judge.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/audit/llm_judge.py
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
    except Exception as exc:
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
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/audit/test_llm_judge.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/audit/llm_judge.py tests/audit/test_llm_judge.py
git commit -m "feat(audit): LLM-as-judge narrative scoring with graceful fallback"
```

---

### Task 7: Markdown report generator

**Files:**
- Create: `src/audit/report.py`
- Test: `tests/audit/test_report.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/audit/test_report.py
from src.audit.checks import Finding
from src.audit.report import render_report


def test_render_report_groups_by_severity():
    findings = [
        Finding("B1001", "blocking", "num_mismatch", "1 元 vs 100 元"),
        Finding("B2003", "suspect", "ref_text_miss", "text not in md"),
        Finding("B1002", "hint", "short_content", "len<30"),
    ]
    md = render_report(findings, totals={"blocking": 1, "suspect": 1, "hint": 1})
    assert "## 阻塞" in md and "B1001" in md
    assert "## 可疑" in md and "B2003" in md
    assert "## 提示" in md and "B1002" in md


def test_render_report_empty_totals_message():
    md = render_report([], totals={"blocking": 0, "suspect": 0, "hint": 0})
    assert "全部通过" in md
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `.venv/bin/python -m pytest tests/audit/test_report.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/audit/report.py
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
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/audit/test_report.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/audit/report.py tests/audit/test_report.py
git commit -m "feat(audit): Markdown report generator grouped by severity"
```

---

### Task 8: CLI orchestrator

**Files:**
- Create: `scripts/audit_results.py`
- Test: integration via `tests/audit/test_integration.py`

- [ ] **Step 1: Write a tiny integration test**

```python
# tests/audit/test_integration.py
"""End-to-end: tiny xlsx + tiny db → audit runs, produces a report."""
from pathlib import Path

import openpyxl
import sqlite3
import subprocess
import sys


def _build_mini_xlsx(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["编号", "问题", "SQL查询语句", "图形格式", "回答"])
    # Good row: number matches SQL
    ws.append([
        "B1001",
        '[{"Q":"金花股份利润总额是多少"}]',
        "SELECT 31400000.0 AS total_profit",
        "无",
        '[{"Q":"x","A":{"content":"利润是 3140 万元。"}}]',
    ])
    # Bad row: number mismatch
    ws.append([
        "B1002",
        '[{"Q":"xx"}]',
        "SELECT 31400000.0 AS total_profit",
        "无",
        '[{"Q":"x","A":{"content":"利润是 99 万元。"}}]',
    ])
    wb.save(path)


def _build_mini_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE income_sheet (total_profit REAL)")
    con.commit()
    con.close()


def test_cli_produces_report(tmp_path: Path):
    xlsx = tmp_path / "result_2.xlsx"
    db = tmp_path / "finance.db"
    report = tmp_path / "audit.md"
    _build_mini_xlsx(xlsx)
    _build_mini_db(db)
    rc = subprocess.run(
        [
            sys.executable,
            "scripts/audit_results.py",
            "--xlsx", str(xlsx),
            "--db", str(db),
            "--out", str(report),
            "--no-judge",
        ],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
    ).returncode
    assert rc == 0
    body = report.read_text(encoding="utf-8")
    assert "阻塞" in body and "B1002" in body
    assert "B1001" not in body or "通过" in body  # B1001 should not be blocking
```

- [ ] **Step 2: Run integration test to confirm failure**

Run: `.venv/bin/python -m pytest tests/audit/test_integration.py -v`
Expected: script not found or non-zero rc.

- [ ] **Step 3: Implement CLI**

```python
# scripts/audit_results.py
"""Audit result xlsx files and emit paper/audit_report.md.

Invoked as: python scripts/audit_results.py --xlsx result_2.xlsx --db data/db/finance.db

Re-runs every row's SQL against the DB, extracts numbers from the content,
checks chart files, validates references, and — for task-3 Hybrid/multi-intent
rows — runs an LLM-as-judge narrative score. Produces a tri-severity
Markdown summary at paper/audit_report.md by default.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openpyxl  # noqa: E402

from src.audit.checks import Finding, check_chart_file, check_number_consistency  # noqa: E402
from src.audit.llm_judge import judge_narrative  # noqa: E402
from src.audit.reference_validator import validate_reference  # noqa: E402
from src.audit.report import render_report  # noqa: E402
from src.audit.sql_runner import SqlRunError, run_sql_strict  # noqa: E402


def _extract_answers(raw: str) -> list[dict]:
    """Parse the 回答 cell, which is either JSON or Python repr."""
    if not raw:
        return []
    try:
        obj = json.loads(raw)
    except ValueError:
        try:
            obj = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return []
    return obj if isinstance(obj, list) else []


_IMG_RE = re.compile(r"\./result/(B\d+_\d+\.jpg)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--db", default=str(ROOT / "data" / "db" / "finance.db"))
    ap.add_argument("--out", default=str(ROOT / "paper" / "audit_report.md"))
    ap.add_argument("--no-judge", action="store_true", help="skip LLM-as-judge")
    args = ap.parse_args()

    xlsx_path = Path(args.xlsx)
    db_path = Path(args.db)
    out_path = Path(args.out)

    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.active
    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    sql_col = "SQL查询语句" if "SQL查询语句" in headers else "SQL查询语法"
    idx = {h: headers.index(h) for h in headers}

    llm = None
    if not args.no_judge:
        try:
            from src.llm.client import LLMClient
            llm = LLMClient.from_env()
        except Exception:
            llm = None

    findings: list[Finding] = []
    totals = {"blocking": 0, "suspect": 0, "hint": 0}

    for row in ws.iter_rows(min_row=2, values_only=True):
        bh = str(row[idx["编号"]] or "").strip()
        if not bh:
            continue
        sql = str(row[idx.get(sql_col, 2)] or "").strip()
        if sql in {"无", "无。"}:
            sql = ""
        answer_raw = str(row[idx.get("回答", len(headers) - 1)] or "")

        # Run SQL once per row (tolerate failure — blocking if non-empty SQL fails)
        try:
            sql_rows = run_sql_strict(db_path, sql) if sql else []
        except SqlRunError as exc:
            findings.append(
                Finding(bh, "blocking", "sql_error", f"SQL execution failed: {exc}")
            )
            sql_rows = []

        # Walk each turn in the answer
        answers = _extract_answers(answer_raw)
        for turn in answers:
            a = (turn or {}).get("A") or {}
            content = str(a.get("content") or "")
            # Numbers
            for f in check_number_consistency(bh, content=content, sql_rows=sql_rows):
                findings.append(f)
            # Chart files
            for m in _IMG_RE.finditer(content):
                img_path = ROOT / "result" / m.group(1)
                for f in check_chart_file(bh, path=img_path):
                    findings.append(f)
            # Images declared in A.image
            for img in (a.get("image") or []):
                img_name = Path(str(img)).name
                img_path = ROOT / "result" / img_name
                for f in check_chart_file(bh, path=img_path):
                    findings.append(f)
            # References (task-3 only)
            refs = a.get("references") or []
            refs_text: list[str] = []
            for ref in refs:
                if not isinstance(ref, dict):
                    continue
                refs_text.append(str(ref.get("text") or ""))
                rr = validate_reference(
                    ref=ref,
                    repo_root=ROOT,
                    ov_root=ROOT / ".openviking",
                )
                if not rr.path_ok:
                    findings.append(
                        Finding(
                            bh, "suspect", "ref_path_missing",
                            f"paper_path not found: {ref.get('paper_path')!r}",
                        )
                    )
                elif not rr.text_ok:
                    findings.append(
                        Finding(
                            bh, "suspect", "ref_text_miss",
                            "reference text not found in any OV chunk",
                        )
                    )
            # Hints
            if content and len(content.strip()) < 30:
                findings.append(
                    Finding(bh, "hint", "short_content", f"content length {len(content)}")
                )
            # LLM-as-judge (Hybrid / multi-intent only heuristic: refs non-empty)
            if llm is not None and refs and not args.no_judge:
                v = judge_narrative(
                    question=str(turn.get("Q") or ""),
                    content=content,
                    references_text=refs_text,
                    llm=llm,
                )
                if v.is_weak():
                    findings.append(
                        Finding(bh, "blocking", "narrative_too_weak",
                                f"LLM judged {v.score}/3: {v.reason}")
                    )

    for f in findings:
        totals[f.severity] += 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_report(findings, totals=totals), encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"  {totals}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run integration test**

Run: `.venv/bin/python -m pytest tests/audit/test_integration.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_results.py tests/audit/test_integration.py
git commit -m "feat(audit): CLI orchestrator and end-to-end integration test"
```

---

### Task 9: Run first real audit on both files

**Files:**
- Create: `paper/audit_report.md` (generated)

- [ ] **Step 1: Regenerate all charts for both files first**

Run:
```bash
.venv/bin/python scripts/regen_charts.py --xlsx result_2.xlsx
.venv/bin/python scripts/regen_charts.py --xlsx result_3.xlsx
```
Expected: each row with chart is re-rendered; no crashes.

- [ ] **Step 2: Run audit for task 2 without LLM-as-judge (cheap first pass)**

Run:
```bash
.venv/bin/python scripts/audit_results.py --xlsx result_2.xlsx --out paper/audit_report_task2.md --no-judge
```
Expected: `wrote paper/audit_report_task2.md`, a totals line printed.

- [ ] **Step 3: Run audit for task 3 without LLM-as-judge**

Run:
```bash
.venv/bin/python scripts/audit_results.py --xlsx result_3.xlsx --out paper/audit_report_task3.md --no-judge
```
Expected: a totals line.

- [ ] **Step 4: Read both reports and decide next steps**

```bash
head -50 paper/audit_report_task2.md
head -80 paper/audit_report_task3.md
```
If blocking / suspect counts match expectations (below a few dozen), proceed.
If thousands of findings, inspect the first few and diagnose before going further.

- [ ] **Step 5: Commit reports + any obvious scaffolding tweaks**

```bash
git add paper/audit_report_task2.md paper/audit_report_task3.md
git commit -m "docs(audit): first-pass audit reports for result_2/3 xlsx"
```

---

### Task 10: Auto-fix: drop broken references

**Files:**
- Create: `scripts/fix_audit_findings.py`
- Test: `tests/audit/test_fix_refs.py`

- [ ] **Step 1: Write failing test**

```python
# tests/audit/test_fix_refs.py
import json
from pathlib import Path

import openpyxl

from scripts.fix_audit_findings import clean_broken_refs_in_cell


def test_clean_refs_drops_bad_paper_path(tmp_path: Path):
    cell = json.dumps(
        [{"Q": "x", "A": {"content": "y", "references": [
            {"paper_path": str(tmp_path / "ok.pdf"), "text": "", "paper_image": ""},
            {"paper_path": str(tmp_path / "missing.pdf"), "text": "", "paper_image": ""},
        ]}}],
        ensure_ascii=False,
    )
    (tmp_path / "ok.pdf").write_bytes(b"x")
    cleaned = clean_broken_refs_in_cell(cell, repo_root=tmp_path, ov_root=tmp_path)
    data = json.loads(cleaned)
    refs = data[0]["A"]["references"]
    assert len(refs) == 1 and refs[0]["paper_path"].endswith("ok.pdf")
```

- [ ] **Step 2: Run test to confirm failure**

Run: `.venv/bin/python -m pytest tests/audit/test_fix_refs.py -v`
Expected: ModuleNotFoundError for `scripts.fix_audit_findings`.

- [ ] **Step 3: Implement (first feature only: clean_broken_refs)**

```python
# scripts/fix_audit_findings.py
"""Auto-apply fixes based on paper/audit_report.md findings.

Subcommands:
  clean-refs    Drop references with broken paper_path or unmatched text
  rewrite       Ask LLM to rewrite content using SQL rows + refs (later tasks)
  reanswer      Run the full text2sql pipeline on a single row (later tasks)

Writes updated xlsx to <input>.audited.xlsx so the original is preserved.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openpyxl  # noqa: E402
from src.audit.reference_validator import validate_reference  # noqa: E402


def _load_cell(raw: str) -> list | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        try:
            return ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return None


def _dump_cell(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def clean_broken_refs_in_cell(raw: str, *, repo_root: Path, ov_root: Path) -> str:
    obj = _load_cell(raw)
    if not isinstance(obj, list):
        return raw
    for turn in obj:
        if not isinstance(turn, dict):
            continue
        A = turn.get("A") or {}
        refs = A.get("references") or []
        kept = []
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            rr = validate_reference(ref=ref, repo_root=repo_root, ov_root=ov_root)
            if rr.path_ok and rr.text_ok:
                kept.append(ref)
        A["references"] = kept
        turn["A"] = A
    return _dump_cell(obj)


def _clean_refs(xlsx_in: Path, xlsx_out: Path, repo_root: Path, ov_root: Path) -> None:
    wb = openpyxl.load_workbook(xlsx_in)
    ws = wb.active
    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    ans_col = headers.index("回答") + 1  # openpyxl is 1-indexed
    for r in range(2, ws.max_row + 1):
        cell = ws.cell(r, ans_col)
        cell.value = clean_broken_refs_in_cell(
            str(cell.value or ""), repo_root=repo_root, ov_root=ov_root
        )
    wb.save(xlsx_out)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("clean-refs")
    p.add_argument("--xlsx", required=True)
    p.add_argument("--out")
    args = ap.parse_args()

    if args.cmd == "clean-refs":
        in_path = Path(args.xlsx)
        out_path = Path(args.out) if args.out else in_path.with_suffix(".audited.xlsx")
        _clean_refs(in_path, out_path, repo_root=ROOT, ov_root=ROOT / ".openviking")
        print(f"wrote {out_path}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test**

Run: `.venv/bin/python -m pytest tests/audit/test_fix_refs.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/fix_audit_findings.py tests/audit/test_fix_refs.py
git commit -m "feat(audit): fix_audit_findings clean-refs drops broken references"
```

---

### Task 11: Auto-fix: rewrite weak content

**Files:**
- Modify: `scripts/fix_audit_findings.py`
- Test: `tests/audit/test_fix_rewrite.py`

- [ ] **Step 1: Write failing test (LLM stubbed)**

```python
# tests/audit/test_fix_rewrite.py
import json
from pathlib import Path

from scripts.fix_audit_findings import rewrite_content_in_cell


class _StubLLM:
    def complete(self, prompt: str, **_) -> str:
        return "重写后的 content：利润总额是 3140 万元。"


def test_rewrite_replaces_only_weak_content():
    cell = json.dumps(
        [{"Q": "利润", "A": {"content": "xyz", "references": []}}],
        ensure_ascii=False,
    )
    out = rewrite_content_in_cell(
        cell,
        sql_rows=[{"total_profit": 31_400_000.0}],
        llm=_StubLLM(),
        weak_ids={0},  # rewrite turn index 0
    )
    data = json.loads(out)
    assert "3140" in data[0]["A"]["content"]


def test_rewrite_keeps_unflagged_turns():
    cell = json.dumps(
        [
            {"Q": "a", "A": {"content": "keep me", "references": []}},
            {"Q": "b", "A": {"content": "rewrite me", "references": []}},
        ],
        ensure_ascii=False,
    )
    out = rewrite_content_in_cell(
        cell, sql_rows=[], llm=_StubLLM(), weak_ids={1},
    )
    data = json.loads(out)
    assert data[0]["A"]["content"] == "keep me"
    assert "重写后" in data[1]["A"]["content"]
```

- [ ] **Step 2: Run test to confirm failure**

Run: `.venv/bin/python -m pytest tests/audit/test_fix_rewrite.py -v`
Expected: `ImportError: cannot import name 'rewrite_content_in_cell'`.

- [ ] **Step 3: Add the rewrite function**

Append to `scripts/fix_audit_findings.py`:

```python
_REWRITE_PROMPT = (
    "你是财报问答助手。基于下列信息重写 content（≤200 字），"
    "必须原样引用 SQL 行的数字（保留小数），不得编造其他数字：\n"
    "问题：{q}\n"
    "SQL 返回行：{s}\n"
    "原 content：{c}\n"
    "只返回重写后的 content 文本，不加引号，不解释。"
)


def rewrite_content_in_cell(raw: str, *, sql_rows: list[dict], llm, weak_ids: set[int]) -> str:
    obj = _load_cell(raw)
    if not isinstance(obj, list):
        return raw
    for i, turn in enumerate(obj):
        if i not in weak_ids or not isinstance(turn, dict):
            continue
        A = turn.get("A") or {}
        prompt = _REWRITE_PROMPT.format(
            q=str(turn.get("Q") or ""),
            s=json.dumps(sql_rows[:10], ensure_ascii=False),
            c=str(A.get("content") or ""),
        )
        try:
            new_content = str(llm.complete(prompt)).strip()
        except Exception:
            continue
        if new_content:
            A["content"] = new_content
            turn["A"] = A
    return _dump_cell(obj)
```

- [ ] **Step 4: Run test**

Run: `.venv/bin/python -m pytest tests/audit/test_fix_rewrite.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/fix_audit_findings.py tests/audit/test_fix_rewrite.py
git commit -m "feat(audit): rewrite weak content via LLM using SQL rows as ground truth"
```

---

### Task 12: Wire rewrite into CLI as second subcommand

**Files:**
- Modify: `scripts/fix_audit_findings.py`

- [ ] **Step 1: Extend `main()` to accept `rewrite` subcommand**

Replace the `main()` in `scripts/fix_audit_findings.py` with:

```python
def _parse_report_for_row_ids(report_path: Path, kinds: set[str]) -> dict[str, set[int]]:
    """Extract {row_id: {turn_ids}} from audit_report.md where kind matches.

    Current report format has no turn-id, so we treat every weak content as
    applying to turn 0. A future format bump can refine this.
    """
    if not report_path.exists():
        return {}
    out: dict[str, set[int]] = {}
    for line in report_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 3:
            continue
        bh, kind = parts[0], parts[1]
        if kind in kinds and bh.startswith("B"):
            out.setdefault(bh, set()).add(0)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("clean-refs")
    p1.add_argument("--xlsx", required=True)
    p1.add_argument("--out")

    p2 = sub.add_parser("rewrite")
    p2.add_argument("--xlsx", required=True)
    p2.add_argument("--db", default=str(ROOT / "data" / "db" / "finance.db"))
    p2.add_argument("--report", required=True)
    p2.add_argument("--out")

    args = ap.parse_args()

    if args.cmd == "clean-refs":
        in_path = Path(args.xlsx)
        out_path = Path(args.out) if args.out else in_path.with_suffix(".audited.xlsx")
        _clean_refs(in_path, out_path, repo_root=ROOT, ov_root=ROOT / ".openviking")
        print(f"wrote {out_path}")
        return 0

    if args.cmd == "rewrite":
        from src.audit.sql_runner import run_sql_strict
        try:
            from src.llm.client import LLMClient
            llm = LLMClient.from_env()
        except Exception:
            print("LLM unavailable; aborting rewrite.", file=sys.stderr)
            return 2
        in_path = Path(args.xlsx)
        out_path = Path(args.out) if args.out else in_path.with_suffix(".rewritten.xlsx")
        weak = _parse_report_for_row_ids(
            Path(args.report), kinds={"num_mismatch", "narrative_too_weak"}
        )
        wb = openpyxl.load_workbook(in_path)
        ws = wb.active
        headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        sql_col_name = "SQL查询语句" if "SQL查询语句" in headers else "SQL查询语法"
        ans_col = headers.index("回答") + 1
        bh_col = headers.index("编号") + 1
        sql_col = headers.index(sql_col_name) + 1
        for r in range(2, ws.max_row + 1):
            bh = str(ws.cell(r, bh_col).value or "").strip()
            if bh not in weak:
                continue
            sql = str(ws.cell(r, sql_col).value or "").strip()
            try:
                sql_rows = run_sql_strict(args.db, sql) if sql and sql != "无" else []
            except Exception:
                sql_rows = []
            cell = ws.cell(r, ans_col)
            cell.value = rewrite_content_in_cell(
                str(cell.value or ""),
                sql_rows=sql_rows,
                llm=llm,
                weak_ids=weak[bh],
            )
        wb.save(out_path)
        print(f"wrote {out_path}  (rewrote {len(weak)} rows)")
        return 0
    return 1
```

- [ ] **Step 2: Smoke-run the subcommands in dry mode on the real files**

Run:
```bash
.venv/bin/python scripts/fix_audit_findings.py clean-refs --xlsx result_3.xlsx --out /tmp/r3.cleaned.xlsx
```
Expected: `wrote /tmp/r3.cleaned.xlsx`. Cells with broken refs lose them; others untouched.

- [ ] **Step 3: Commit**

```bash
git add scripts/fix_audit_findings.py
git commit -m "feat(audit): fix_audit_findings rewrite subcommand driven by audit report"
```

---

### Task 13: Iterate: fix → re-audit → confirm blocking = 0

**Files:**
- Update: `result_2.xlsx`, `result_3.xlsx`, `paper/audit_report_task*.md`

- [ ] **Step 1: Apply clean-refs to both files**

Run:
```bash
.venv/bin/python scripts/fix_audit_findings.py clean-refs --xlsx result_2.xlsx --out result_2.cleaned.xlsx
.venv/bin/python scripts/fix_audit_findings.py clean-refs --xlsx result_3.xlsx --out result_3.cleaned.xlsx
```

- [ ] **Step 2: Re-audit the cleaned files**

Run:
```bash
.venv/bin/python scripts/audit_results.py --xlsx result_2.cleaned.xlsx --out paper/audit_report_task2.md --no-judge
.venv/bin/python scripts/audit_results.py --xlsx result_3.cleaned.xlsx --out paper/audit_report_task3.md --no-judge
```
Expected: suspect count (refs) drops to near-zero.

- [ ] **Step 3: Apply rewrite pass on any remaining blocking rows**

Run:
```bash
.venv/bin/python scripts/fix_audit_findings.py rewrite \
    --xlsx result_2.cleaned.xlsx \
    --report paper/audit_report_task2.md \
    --out result_2.rewritten.xlsx
.venv/bin/python scripts/fix_audit_findings.py rewrite \
    --xlsx result_3.cleaned.xlsx \
    --report paper/audit_report_task3.md \
    --out result_3.rewritten.xlsx
```

- [ ] **Step 4: Final audit with LLM-as-judge ON**

Run:
```bash
.venv/bin/python scripts/audit_results.py --xlsx result_2.rewritten.xlsx --out paper/audit_report_task2.md
.venv/bin/python scripts/audit_results.py --xlsx result_3.rewritten.xlsx --out paper/audit_report_task3.md
```
Expected: `blocking = 0` in the totals line; a handful of suspect/hint is OK.

- [ ] **Step 5: If blocking > 0, inspect the specific rows and decide: re-run rewrite, hand-edit, or declare acceptable**

- [ ] **Step 6: Rename rewritten files over the originals and commit**

```bash
mv result_2.rewritten.xlsx result_2.xlsx
mv result_3.rewritten.xlsx result_3.xlsx
rm -f result_2.cleaned.xlsx result_3.cleaned.xlsx
git add result_2.xlsx result_3.xlsx paper/audit_report_task2.md paper/audit_report_task3.md
git commit -m "fix(audit): clean broken refs and rewrite weak content; blocking=0"
```

---

### Task 14: Push to GitHub

- [ ] **Step 1: Verify pytest suite is still green**

Run: `.venv/bin/python -m pytest tests/ -v --ignore=tests/test_research_qa.py`
Expected: all pass (the one skipped test file is untouched and requires LLM).

- [ ] **Step 2: Push**

Run: `git push origin master`
Expected: push succeeds, Railway picks up latest. No further action needed.

---

## Self-review

**1. Spec coverage**

| Spec item | Covered by |
| :-- | :-- |
| audit_results.py | Tasks 1–8 |
| regen_charts.py --all | Task 9 (we reuse existing script — no `--all` flag needed) |
| fix_audit_findings.py | Tasks 10–12 |
| LLM-as-judge | Task 6 (module) + Task 8 (wired in CLI) + Task 13 (run with judge on) |
| num_mismatch check | Task 4 |
| chart file check | Task 4 |
| reference validator | Task 5 |
| report Markdown | Task 7 |
| fix: clean_refs | Task 10 |
| fix: rewrite | Tasks 11–12 |
| fix: reanswer | **Not implemented.** Rationale: existing `pipeline.py --task answer/research` already produces a full xlsx; if `rewrite` cannot salvage a row, the fallback is to edit by hand or re-run pipeline for a single row via a small one-off. Flagging as out-of-scope for this plan. |
| end-to-end integration test | Task 8 |
| final blocking=0 assertion | Task 13 |

**2. Placeholder scan** — no TBDs, every code step shows complete code.

**3. Type consistency** — `Finding` fields consistent across `checks.py`, `report.py`, `audit_results.py`; `JudgeVerdict` used only in `llm_judge.py` and integrated via `.is_weak()`; `RefResult` only in `reference_validator.py` and consumed once in the CLI.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-19-result-audit.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
