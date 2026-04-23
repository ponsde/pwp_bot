"""Task 3 research smoke for paper eval: citation validity + B2005 multi-turn trace."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


QUESTIONS = [
    ("R1", "归因分析", [
        {"Q": "片仔癀利润总额是多少"},
        {"Q": "2025年第三季度的"},
        {"Q": "同比增长还是下降了？为什么"},
    ]),
    ("R2", "归因分析", [{"Q": "华润三九2024年净利润同比增长的原因是什么"}]),
    ("R3", "归因分析", [{"Q": "白云山2024年营业收入下滑的主要原因是什么"}]),
    ("R4", "行业趋势", [{"Q": "中药板块2024年的整体盈利能力变化趋势和政策背景"}]),
    ("R5", "归因分析", [{"Q": "云南白药近几年毛利率变化的原因"}]),
]


def main() -> None:
    rows = [{"编号": qid, "问题类型": qtype, "问题": json.dumps(turns, ensure_ascii=False)}
            for qid, qtype, turns in QUESTIONS]
    out = Path("data/smoke_research.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(out, index=False)
    print(f"wrote {out} ({len(rows)} questions)")


if __name__ == "__main__":
    main()
