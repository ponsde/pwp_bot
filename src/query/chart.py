"""Rule-based chart selection and rendering."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Chinese font support — try common CJK fonts, fall back gracefully
_FONT_CANDIDATES = [
    "SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC",
    "Microsoft YaHei", "PingFang SC", "Source Han Sans SC",
]
for _font in _FONT_CANDIDATES:
    try:
        matplotlib.font_manager.findfont(_font, fallback_to_default=False)
        plt.rcParams["font.sans-serif"] = [_font] + plt.rcParams.get("font.sans-serif", [])
        plt.rcParams["axes.unicode_minus"] = False
        break
    except Exception:
        continue


def select_chart_type(question: str, rows: Sequence[dict]) -> str:
    if any(token in question for token in ["趋势", "变化", "历年", "季度", "走势", "近几年"]):
        return "line"
    if any(token in question for token in ["占比", "构成", "份额", "比例"]):
        return "pie"
    if any(token in question for token in ["对比", "比较", "排名", "top"]):
        return "bar"
    if len(rows) > 1:
        return "bar"
    return "none"


def render_chart(
    chart_type: str,
    rows: Sequence[dict],
    output_path: str,
    title: str = "",
) -> str | None:
    if chart_type == "none" or not rows:
        return None

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    labels = [str(row.get("label", idx)) for idx, row in enumerate(rows, start=1)]
    values = [float(row.get("value", 0) or 0) for row in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    if chart_type == "line":
        ax.plot(labels, values, marker="o", linewidth=2)
        for i, v in enumerate(values):
            ax.annotate(f"{v:,.0f}", (labels[i], v), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)
    elif chart_type == "pie":
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    else:
        bars = ax.bar(labels, values, color="#4C8BF5")
        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{v:,.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_title(title, fontsize=12)
    if chart_type != "pie":
        ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(path, format="jpg", dpi=150)
    plt.close(fig)
    return str(path)
