"""Rule-based chart selection and rendering."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

logger = logging.getLogger(__name__)

# Chinese font support — try common CJK fonts, fall back gracefully
_FONT_CANDIDATES = [
    "SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC",
    "Microsoft YaHei", "PingFang SC", "Source Han Sans SC",
]
_FALLBACK_FONT_PATH = Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc")


def _configure_cjk_font(
    fallback_font_path: Path | None = None,
) -> str | None:
    """Configure matplotlib CJK font, falling back to a known system font path.

    Returns the selected font family name/path when configured, otherwise None.
    """
    for font_name in _FONT_CANDIDATES:
        try:
            font_manager.findfont(font_name, fallback_to_default=False)
        except Exception:
            continue

        plt.rcParams["font.sans-serif"] = [font_name] + plt.rcParams.get("font.sans-serif", [])
        plt.rcParams["axes.unicode_minus"] = False
        return font_name

    fallback_path = fallback_font_path or _FALLBACK_FONT_PATH
    if fallback_path.exists():
        try:
            font_properties = font_manager.FontProperties(fname=str(fallback_path))
            font_name = font_properties.get_name()
            current_fonts = plt.rcParams.get("font.sans-serif", [])
            plt.rcParams["font.sans-serif"] = [font_name] + [font for font in current_fonts if font != font_name]
            plt.rcParams["axes.unicode_minus"] = False
            return str(fallback_path)
        except Exception as exc:
            logger.warning("Failed to load fallback CJK font from %s: %s", fallback_path, exc)

    logger.warning(
        "No CJK font found; matplotlib default font will be used and Chinese characters may not render correctly."
    )
    return None


_configure_cjk_font()


def pick_chart_columns(row: dict) -> tuple[str | None, object | None]:
    """Intelligently select label and value columns from a result row for charting."""
    preferred_label_fields = ["stock_abbr", "report_period"]
    preferred_value_fields = ["yoy_ratio"]

    label_field = next((field for field in preferred_label_fields if field in row and row.get(field) not in (None, "")), None)
    if label_field is None:
        for key, value in row.items():
            if isinstance(value, str) and value != "":
                label_field = key
                break
        if label_field is None and row:
            label_field = next(iter(row.keys()))

    value_field = next((field for field in preferred_value_fields if isinstance(row.get(field), (int, float))), None)
    if value_field is None:
        numeric_keys = [key for key, value in row.items() if isinstance(value, (int, float)) and key != label_field]
        if numeric_keys:
            value_field = numeric_keys[-1]
        elif label_field and isinstance(row.get(label_field), (int, float)):
            value_field = label_field

    label = str(row.get(label_field)) if label_field and row.get(label_field) not in (None, "") else None
    value = row.get(value_field) if value_field else None
    return label, value


def safe_chart_data(rows: Sequence[dict]) -> list[dict]:
    """Build chart-friendly data with smart label/value column selection."""
    data = []
    for row in rows:
        label, value = pick_chart_columns(row)
        if value is None:
            continue
        if label is None:
            label = str(len(data) + 1)
        try:
            data.append({"label": label, "value": float(value)})
        except (ValueError, TypeError):
            continue
    return data


def select_chart_type(question: str, rows: Sequence[dict]) -> str:
    if len(rows) <= 1:
        return "none"
    if any(token in question for token in ["趋势", "变化", "历年", "季度", "走势", "近几年"]):
        return "line"
    if any(token in question for token in ["占比", "构成", "份额", "比例"]):
        return "pie"
    if any(token in question for token in ["对比", "比较", "排名", "top", "绘图", "可视化", "画图", "图表"]):
        return "bar"
    if len(rows) > 1:
        return "bar"
    return "none"


def _detect_unit_scale(values: Sequence[float]) -> tuple[float, str]:
    """Detect appropriate unit scale based on max absolute value."""
    max_abs = max((abs(v) for v in values), default=0)
    if max_abs >= 1e8:
        return 1e8, "亿元"
    if max_abs >= 1e4:
        return 1e4, "万元"
    return 1.0, ""


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
    raw_values = [float(row.get("value", 0) or 0) for row in rows]

    divisor, unit_label = _detect_unit_scale(raw_values)
    values = [v / divisor for v in raw_values]

    fig, ax = plt.subplots(figsize=(8, 5))
    if chart_type == "line":
        ax.plot(labels, values, marker="o", linewidth=2)
        for i, v in enumerate(values):
            ax.annotate(f"{v:,.2f}", (labels[i], v), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)
    elif chart_type == "pie":
        ax.pie(raw_values, labels=labels, autopct="%1.1f%%", startangle=90)
    else:
        bars = ax.bar(labels, values, color="#4C8BF5")
        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{v:,.2f}", ha="center", va="bottom", fontsize=8)
    ax.set_title(title, fontsize=12)
    if chart_type != "pie":
        ax.tick_params(axis="x", rotation=30)
        if unit_label:
            ax.set_ylabel(unit_label)
    fig.tight_layout()
    fig.savefig(path, format="jpg", dpi=150)
    plt.close(fig)
    return str(path)
