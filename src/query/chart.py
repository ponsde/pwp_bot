"""Rule-based chart selection and rendering."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def select_chart_type(question: str, rows: Sequence[dict]) -> str:
    q = question.lower()
    if any(token in question for token in ["趋势", "变化", "历年", "季度", "走势"]):
        return "line"
    if any(token in question for token in ["占比", "构成", "份额"]):
        return "pie"
    if len(rows) > 1:
        return "bar"
    return "none"


def render_chart(chart_type: str, rows: Sequence[dict], output_path: str, title: str = "") -> str | None:
    if chart_type == "none" or not rows:
        return None

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    labels = [str(row.get("label", row.get("x", idx))) for idx, row in enumerate(rows, start=1)]
    values = [float(row.get("value", row.get("y", 0)) or 0) for row in rows]

    fig, ax = plt.subplots(figsize=(6, 4))
    if chart_type == "line":
        ax.plot(labels, values, marker="o")
    elif chart_type == "pie":
        ax.pie(values, labels=labels, autopct="%1.1f%%")
    else:
        ax.bar(labels, values)
    ax.set_title(title)
    if chart_type != "pie":
        ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(path, format="jpg")
    plt.close(fig)
    return str(path)
