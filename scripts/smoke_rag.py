"""Re-smoke P9 + P10 to verify openviking_search gets invoked on attribution."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


QUESTIONS = [
    ("R9", "归因分析", [{"Q": "华润三九2024年净利润同比增长的原因是什么"}]),
    ("R10", "归因分析", [
        {"Q": "片仔癀利润总额是多少"},
        {"Q": "2025年第三季度的"},
        {"Q": "同比增长还是下降了？为什么"},
    ]),
]


def main() -> None:
    rows = [{"编号": qid, "问题类型": qtype, "问题": json.dumps(turns, ensure_ascii=False)}
            for qid, qtype, turns in QUESTIONS]
    out = Path("data/smoke_rag.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(out, index=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
