"""Smoke the exact Railway-failing question: multi-period yoy trend."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


QUESTIONS = [
    ("S6", "数据统计分析查询", [{"Q": "白云山（600332）2022年至2025年第三季度的营业总收入同比增长率"}]),
    ("S7", "数据统计分析查询", [{"Q": "华润三九近几年净利润同比增长率变化"}]),
]


def main() -> None:
    rows = [{"编号": qid, "问题类型": qtype, "问题": json.dumps(turns, ensure_ascii=False)}
            for qid, qtype, turns in QUESTIONS]
    out = Path("data/smoke_yoy_trend.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(out, index=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
