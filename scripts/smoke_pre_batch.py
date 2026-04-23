"""10-question pre-batch smoke covering all critical paths after OV fix."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


QUESTIONS = [
    ("P1", "数据基本查询", [{"Q": "白云山2025Q3营业总收入是多少"}]),
    ("P2", "数据基本查询", [{"Q": "2025年前三季度营业收入超过200亿的中药上市公司有哪些？"}]),
    ("P3", "数据基本查询", [{"Q": "华润三九2025年前三季度净利润同比增长率是多少"}]),
    ("P4", "数据统计分析查询", [
        {"Q": "净利润最高的5家中药上市公司"},
        {"Q": "那2025年前三季度的呢"},
    ]),
    ("P5", "图表生成", [{"Q": "画出华润三九近几年营业收入的趋势图"}]),
    ("P6", "数据基本查询", [{"Q": "白云山（600332）2025Q3净利润是多少"}]),
    ("P7", "数据基本查询", [{"Q": "净利润是多少"}]),  # clarification
    ("P8", "数据统计分析查询", [{"Q": "白云山（600332）2022年至2025年第三季度的营业总收入同比增长率"}]),
    ("P9", "归因分析", [{"Q": "华润三九2024年净利润同比增长的原因是什么"}]),  # tests openviking_search
    ("P10", "归因分析", [
        {"Q": "片仔癀利润总额是多少"},
        {"Q": "2025年第三季度的"},
        {"Q": "同比增长还是下降了？为什么"},
    ]),
]


def main() -> None:
    rows = [{"编号": qid, "问题类型": qtype, "问题": json.dumps(turns, ensure_ascii=False)}
            for qid, qtype, turns in QUESTIONS]
    out = Path("data/smoke_pre_batch.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(out, index=False)
    print(f"wrote {out} ({len(rows)} questions)")


if __name__ == "__main__":
    main()
