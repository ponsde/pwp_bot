"""Re-smoke S3 ranking (should be 柱状图) + S4 trend (折线图) after chart fix."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


QUESTIONS = [
    ("S3", "数据统计分析查询", [
        {"Q": "净利润最高的5家中药上市公司"},
        {"Q": "那2025年前三季度的呢"},
    ]),
    ("S4", "图表生成", [{"Q": "画出华润三九近几年营业收入的趋势图"}]),
]


def main() -> None:
    rows = [{"编号": qid, "问题类型": qtype, "问题": json.dumps(turns, ensure_ascii=False)}
            for qid, qtype, turns in QUESTIONS]
    out = Path("data/smoke_charts.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(out, index=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
