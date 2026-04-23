"""Full 7-question smoke covering all post-review fixes."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


QUESTIONS = [
    # threshold — baseline
    ("S1", "数据基本查询", [{"Q": "2025年前三季度营业收入超过200亿的中药上市公司有哪些？"}]),
    # Q3 yoy precomputed column path
    ("S2", "数据基本查询", [{"Q": "华润三九2025年前三季度净利润同比增长率是多少"}]),
    # multi-turn top_n inheritance + retry session replay if triggered
    ("S3", "数据统计分析查询", [
        {"Q": "净利润最高的5家中药上市公司"},
        {"Q": "那2025年前三季度的呢"},
    ]),
    # trend chart — must be 折线图 via row-shape heuristic
    ("S4", "图表生成", [{"Q": "画出华润三九近几年营业收入的趋势图"}]),
    # bracket stock code
    ("S5", "数据基本查询", [{"Q": "白云山（600332）2025Q3净利润是多少"}]),
    # multi-period yoy trend — previously drifted to sandbox matplotlib
    ("S6", "数据统计分析查询", [{"Q": "白云山（600332）2022年至2025年第三季度的营业总收入同比增长率"}]),
    # clarification — MCP query must return the clarification, not "未查询到"
    ("S7", "数据基本查询", [{"Q": "净利润是多少"}]),
]


def main() -> None:
    rows = [{"编号": qid, "问题类型": qtype, "问题": json.dumps(turns, ensure_ascii=False)}
            for qid, qtype, turns in QUESTIONS]
    out = Path("data/smoke_full.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(out, index=False)
    print(f"wrote {out} ({len(rows)} questions)")


if __name__ == "__main__":
    main()
