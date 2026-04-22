"""Generate a 5-question smoke xlsx to validate the 4 post-review fixes.

Covers:
  S1 — threshold query + top ranking (regression baseline)
  S2 — Q3 yoy (text2sql._build_yoy_sql regex fix)
  S3 — multi-turn top_n inheritance (conversation.merge_intent fix)
  S4 — chart generation (chart_type → Chinese 折线图 via batch_via_bot fix)
  S5 — bracket stock code handling (regression baseline)
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


QUESTIONS = [
    ("S1", "数据基本查询", [{"Q": "2025年前三季度营业收入超过200亿的中药上市公司有哪些？"}]),
    ("S2", "数据基本查询", [{"Q": "华润三九2025年前三季度净利润同比增长率是多少"}]),
    ("S3", "数据统计分析查询", [
        {"Q": "净利润最高的5家中药上市公司"},
        {"Q": "那2025年前三季度的呢"},
    ]),
    ("S4", "图表生成", [{"Q": "画出华润三九近几年营业收入的趋势图"}]),
    ("S5", "数据基本查询", [{"Q": "白云山（600332）2025Q3净利润是多少"}]),
]


def main() -> None:
    rows = [{"编号": qid, "问题类型": qtype, "问题": json.dumps(turns, ensure_ascii=False)}
            for qid, qtype, turns in QUESTIONS]
    out = Path("data/smoke_questions.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(out, index=False)
    print(f"wrote {out} ({len(rows)} questions)")


if __name__ == "__main__":
    main()
