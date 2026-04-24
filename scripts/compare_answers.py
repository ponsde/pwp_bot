"""Compare two result xlsx files produced by pipeline --task answer.

Flags:
  - Questions where one run has an error/NULL answer and the other has data.
  - Questions where numeric values in the answer text differ significantly.
  - Questions where the SQL differs (useful for tracing root-cause shifts).

Usage:
    python3 scripts/compare_answers.py path/to/old.xlsx path/to/new.xlsx
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import openpyxl


NUMERIC_RE = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")
ERROR_MARKERS = ("查询失败", "请补充信息", "未找到", "无结果", "无相关数据", "错误", "失败")


def _load(path: str) -> dict[str, dict]:
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    out: dict[str, dict] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        qid = str(row[0]).strip()
        q_raw = row[1]
        sql = row[2] or ""
        ans_raw = row[4] or "[]"
        out[qid] = {"q": q_raw, "sql": sql, "ans_raw": ans_raw}
    wb.close()
    return out


def _extract_answer_content(ans_raw: str) -> str:
    """Flatten the JSON answer payload into one content string."""
    try:
        parsed = json.loads(ans_raw)
    except Exception:
        return ans_raw
    if not isinstance(parsed, list):
        return ans_raw
    chunks: list[str] = []
    for turn in parsed:
        if isinstance(turn, dict):
            a = turn.get("A")
            if isinstance(a, dict):
                content = a.get("content") or ""
                chunks.append(content)
            elif isinstance(a, str):
                chunks.append(a)
    return "\n---\n".join(chunks)


def _extract_numbers(text: str) -> list[float]:
    out: list[float] = []
    for s in NUMERIC_RE.findall(text):
        try:
            out.append(float(s.replace(",", "")))
        except ValueError:
            pass
    return out


def _classify(content: str) -> str:
    for m in ERROR_MARKERS:
        if m in content:
            return "error"
    if not content.strip():
        return "empty"
    return "ok"


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    old_path, new_path = sys.argv[1:]
    old = _load(old_path)
    new = _load(new_path)

    common = sorted(set(old) & set(new))
    print(f"Loaded: old={len(old)}  new={len(new)}  common={len(common)}")

    fixed, regressed, num_shift, sql_shift = [], [], [], []
    both_ok_same = 0

    for qid in common:
        old_content = _extract_answer_content(old[qid]["ans_raw"])
        new_content = _extract_answer_content(new[qid]["ans_raw"])
        old_cls = _classify(old_content)
        new_cls = _classify(new_content)

        if old_cls == "error" and new_cls == "ok":
            fixed.append(qid)
        elif old_cls == "ok" and new_cls == "error":
            regressed.append(qid)

        if old_cls == "ok" and new_cls == "ok":
            old_nums = set(round(n, 2) for n in _extract_numbers(old_content))
            new_nums = set(round(n, 2) for n in _extract_numbers(new_content))
            only_old = old_nums - new_nums
            only_new = new_nums - old_nums
            if only_old or only_new:
                num_shift.append((qid, only_old, only_new))
            else:
                both_ok_same += 1

        if old[qid]["sql"] != new[qid]["sql"]:
            sql_shift.append(qid)

    print(f"\n=== Summary ===")
    print(f"error->ok (fixed):     {len(fixed)}")
    print(f"ok->error (regressed): {len(regressed)}")
    print(f"numeric differences:   {len(num_shift)}")
    print(f"SQL changed:           {len(sql_shift)}")
    print(f"both ok, same numbers: {both_ok_same}")

    if fixed:
        print(f"\n=== FIXED (was error, now ok) ===")
        for qid in fixed[:20]:
            print(f"  {qid}")
    if regressed:
        print(f"\n=== REGRESSED (was ok, now error) ===")
        for qid in regressed[:20]:
            print(f"  {qid}")
    if num_shift:
        print(f"\n=== Top numeric shifts (sample 15) ===")
        for qid, only_old, only_new in num_shift[:15]:
            ods = sorted(only_old)[:5]
            nds = sorted(only_new)[:5]
            print(f"  {qid}: old-only={ods}  new-only={nds}")


if __name__ == "__main__":
    main()
