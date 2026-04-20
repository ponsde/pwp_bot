"""Compare multiple audit_db.json outputs side-by-side.

Usage:
    python3 scripts/audit_compare.py label1=path1.json label2=path2.json ...
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _summarize(audit: dict) -> dict:
    bal = audit["balance_equation"]
    cross = audit["cross_table_consistency"]
    cov = audit["coverage"]["core_performance_indicators_sheet"]
    nulls = audit["null_rates"]

    bal_rel = [r["rel_error"] for r in bal]
    cross_rel = [r["rel_error"] for r in cross]

    return {
        "rows": cov["rows"],
        "companies": cov["companies"],
        "periods": cov["periods"],
        "balance_count": len(bal),
        "balance_median_rel": round(sorted(bal_rel)[len(bal_rel)//2], 4) if bal_rel else 0,
        "balance_sum_rel": round(sum(bal_rel), 2),
        "balance_garbage_lt100": sum(1 for r in bal if abs(r["assets"]) < 100),
        "cross_count": len(cross),
        "cross_median_rel": round(sorted(cross_rel)[len(cross_rel)//2], 4) if cross_rel else 0,
        "cross_sum_rel": round(sum(cross_rel), 2),
        "cross_similar_magnitude": sum(1 for r in cross if r["core_net_profit"] != 0 and 0.5 <= abs(r["income_net_profit"]/r["core_net_profit"]) <= 2),
        "cross_unit_mismatch": sum(1 for r in cross if r["core_net_profit"] != 0 and abs(r["income_net_profit"]/r["core_net_profit"]) > 100),
        "missing_periods": len(audit["missing_periods"]),
        "yoy_outliers": len(audit["yoy_outliers"]),
        "null_income_total_profit": nulls.get("income_sheet", {}).get("total_profit", 0),
        "null_balance_liab": nulls.get("balance_sheet", {}).get("liability_total_liabilities", 0),
        "null_balance_equity": nulls.get("balance_sheet", {}).get("equity_total_equity", 0),
    }


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("usage: audit_compare.py label1=path1.json label2=path2.json ...")
        sys.exit(1)
    labels, summaries = [], []
    for arg in args:
        if "=" not in arg:
            print(f"expected label=path, got {arg}")
            sys.exit(1)
        label, path = arg.split("=", 1)
        with Path(path).open(encoding="utf-8") as f:
            audit = json.load(f)
        labels.append(label)
        summaries.append(_summarize(audit))

    keys = list(summaries[0].keys())
    col_width = max(22, max(len(l) for l in labels) + 2)

    print(f"{'metric':40s}" + "".join(f"{l:>{col_width}}" for l in labels))
    for key in keys:
        row = f"{key:40s}"
        for s in summaries:
            v = s[key]
            if isinstance(v, float):
                row += f"{v:>{col_width},.4f}" if abs(v) < 1 else f"{v:>{col_width},.2f}"
            else:
                row += f"{v:>{col_width},}"
        print(row)


if __name__ == "__main__":
    main()
