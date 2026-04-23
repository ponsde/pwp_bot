"""Rule-based chart selection and rendering."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from src.query.answer import _format_report_period, _FIELD_UNITS

logger = logging.getLogger(__name__)

# Chinese font support — covers common CJK font names across OSes.
# fonts-noto-cjk on Debian/Ubuntu (our Dockerfile) registers as the JP
# variant even though the .ttc covers SC/TC/JP/KR glyphs, so include it.
_FONT_CANDIDATES = [
    "Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans CJK",
    "Noto Serif CJK SC", "Noto Serif CJK JP",
    "WenQuanYi Micro Hei", "WenQuanYi Zen Hei",
    "SimHei", "Microsoft YaHei", "PingFang SC",
    "Source Han Sans SC", "Source Han Sans CN",
    "Hiragino Sans GB",
]
# Filesystem fallbacks. First-match wins. Covers Debian/Ubuntu package
# layouts for fonts-noto-cjk and fonts-wqy-microhei, plus macOS.
_FALLBACK_FONT_PATHS = [
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
]


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
        logger.info("CJK font configured: %s", font_name)
        return font_name

    candidates = [fallback_font_path] if fallback_font_path else list(_FALLBACK_FONT_PATHS)
    for fallback_path in candidates:
        if fallback_path is None or not fallback_path.exists():
            continue
        try:
            font_properties = font_manager.FontProperties(fname=str(fallback_path))
            font_name = font_properties.get_name()
            current_fonts = plt.rcParams.get("font.sans-serif", [])
            plt.rcParams["font.sans-serif"] = [font_name] + [f for f in current_fonts if f != font_name]
            plt.rcParams["axes.unicode_minus"] = False
            # Best-effort: also register with fontManager so findfont() later
            # resolves glyph paths correctly. Not fatal if it fails (tests pass
            # fake files that won't load).
            try:
                font_manager.fontManager.addfont(str(fallback_path))
            except Exception:
                pass
            logger.info("CJK font configured from file: %s (%s)", font_name, fallback_path)
            return str(fallback_path)
        except Exception as exc:
            logger.warning("Failed to load CJK font from %s: %s", fallback_path, exc)

    logger.warning(
        "No CJK font found; matplotlib default font will be used and Chinese characters may not render correctly."
    )
    return None


_configure_cjk_font()


_VALUE_FIELD_PRIORITY_SUFFIXES = ("_yoy_growth", "_yoy", "_ratio", "_rate", "_margin", "_qoq_growth")


def _pick_global_value_field(
    rows: Sequence[dict],
    label_field: str | None,
) -> str | None:
    """Pick a single value_field across all rows.

    Rationale: picking per-row causes NULL cells to silently fall back to
    another numeric column (e.g. yoy=NULL → revenue), which mixes quantities
    on one axis and produces ghost "0.00万元" points on the chart. Fix is
    one field globally; rows NULL in that field get skipped, not reassigned.

    Preference order:
      1. Columns whose name ends with a rate-like suffix (_yoy_growth, _ratio…)
         — these are the semantically most interesting "chartable" metrics.
      2. Among the remaining numeric columns, pick the one with most non-null
         values across rows.
      3. Ties fall back to SQL order (dict insertion order).
    """
    if not rows:
        return None
    candidate_coverage: dict[str, int] = {}
    for row in rows:
        for key, val in row.items():
            if key == label_field:
                continue
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                candidate_coverage[key] = candidate_coverage.get(key, 0) + 1
    if not candidate_coverage:
        return None
    priority_matches = [k for k in candidate_coverage if any(k.endswith(s) for s in _VALUE_FIELD_PRIORITY_SUFFIXES)]
    if priority_matches:
        # Among priority-suffix columns, pick the one with most non-null coverage.
        return max(priority_matches, key=lambda k: (candidate_coverage[k], -list(candidate_coverage).index(k)))
    # Otherwise pick whichever numeric column has broadest coverage; ties go to SQL order.
    return max(candidate_coverage, key=lambda k: (candidate_coverage[k], -list(candidate_coverage).index(k)))


def pick_chart_columns(
    row: dict,
    preferred_label_fields: Sequence[str] = ("stock_abbr", "report_period"),
    value_field_override: str | None = None,
) -> tuple[str | None, object | None, str | None, str | None]:
    """Intelligently select label and value columns from a result row for charting.

    If ``value_field_override`` is provided, that column is used as-is and the
    per-row fallback (to another numeric column) is suppressed — rows where the
    chosen column is NULL return value=None so safe_chart_data can skip them.
    """
    preferred_value_fields = ["yoy_ratio"]

    label_field = next((field for field in preferred_label_fields if field in row and row.get(field) not in (None, "")), None)
    if label_field is None:
        for key, value in row.items():
            if isinstance(value, str) and value != "":
                label_field = key
                break
        if label_field is None and row:
            label_field = next(iter(row.keys()))

    if value_field_override is not None:
        value_field = value_field_override
    else:
        value_field = next((field for field in preferred_value_fields if isinstance(row.get(field), (int, float))), None)
        if value_field is None:
            numeric_keys = [key for key, value in row.items() if isinstance(value, (int, float)) and key != label_field]
            if numeric_keys:
                value_field = numeric_keys[-1]
            elif label_field and isinstance(row.get(label_field), (int, float)):
                value_field = label_field

    label = None
    if label_field and row.get(label_field) not in (None, ""):
        label_value = row.get(label_field)
        label = _format_report_period(label_value) if label_field == "report_period" else str(label_value)
    raw_value = row.get(value_field) if value_field else None
    # When override is set, NULL in that column must stay NULL so caller skips
    # the row — do not silently substitute another numeric column.
    if value_field_override is not None and not isinstance(raw_value, (int, float)):
        raw_value = None
    return label, raw_value, label_field, value_field


def safe_chart_data(rows: Sequence[dict]) -> tuple[list[dict], str | None]:
    """Build chart-friendly data with smart label/value column selection.

    Returns (data, value_field) so callers can pass field context to render_chart.
    """
    # Row-shape-aware label preference: a single company across many periods
    # wants report_period on the x-axis; a single period across many companies
    # wants stock_abbr.
    preferred: tuple[str, ...] = ("stock_abbr", "report_period")
    if rows and isinstance(rows[0], dict):
        abbrs = {r.get("stock_abbr") for r in rows if r.get("stock_abbr")}
        periods = {r.get("report_period") for r in rows if r.get("report_period")}
        if len(periods) >= 2 and len(abbrs) <= 1:
            preferred = ("report_period", "stock_abbr")
        elif len(abbrs) >= 2 and len(periods) <= 1:
            preferred = ("stock_abbr", "report_period")

    # Probe the label field from the first row to compute a global value_field
    # that's used by every row — prevents NULL→fallback quantity mixing.
    probe_label_field: str | None = None
    if rows and isinstance(rows[0], dict):
        probe_label_field = next(
            (f for f in preferred if f in rows[0] and rows[0].get(f) not in (None, "")),
            None,
        )
    global_value_field = _pick_global_value_field(rows, probe_label_field)

    data = []
    detected_value_field: str | None = None
    for row in rows:
        label, value, _, value_field = pick_chart_columns(
            row, preferred, value_field_override=global_value_field
        )
        if value is None:
            continue
        if label is None:
            label = str(len(data) + 1)
        if detected_value_field is None and value_field:
            detected_value_field = value_field
        try:
            data.append({"label": label, "value": float(value)})
        except (ValueError, TypeError):
            continue
    return data, detected_value_field


def select_chart_type(question: str, rows: Sequence[dict]) -> str:
    if len(rows) <= 1:
        return "none"
    # Row-shape wins over question keywords: ranking-style rows (many distinct
    # companies, one period) should always be bar, even when the follow-up
    # question only mentions the period ("那2025年前三季度的呢" inherits top_n
    # from an earlier turn so select_chart_type can't tell from text alone).
    if rows and isinstance(rows[0], dict):
        abbrs = {r.get("stock_abbr") for r in rows if r.get("stock_abbr")}
        periods = {r.get("report_period") for r in rows if r.get("report_period")}
        if len(abbrs) >= 3 and len(periods) <= 1:
            return "bar"
        if len(abbrs) <= 1 and len(periods) >= 3:
            return "line"
    if any(token in question for token in ["占比", "构成", "份额", "比例"]):
        return "pie"
    if any(token in question for token in ["对比", "比较", "排名", "top", "绘图", "可视化", "画图", "图表"]):
        return "bar"
    if any(token in question for token in ["趋势", "变化", "历年", "走势", "近几年"]):
        return "line"
    if len(rows) > 1:
        return "bar"
    return "none"


def _detect_unit_scale(values: Sequence[float], base_unit: str = "") -> tuple[float, str]:
    """Detect appropriate unit scale based on max absolute value and field's base unit."""
    max_abs = max((abs(v) for v in values), default=0)
    if base_unit == "万元":
        # Data is already in 万元; only scale up to 亿元
        if max_abs >= 1e4:
            return 1e4, "亿元"
        return 1.0, "万元"
    if base_unit == "元":
        if max_abs >= 1e8:
            return 1e8, "亿元"
        if max_abs >= 1e4:
            return 1e4, "万元"
        return 1.0, "元"
    # Unknown or non-monetary unit (e.g. %, ratio)
    if max_abs >= 1e8:
        return 1e8, "亿元"
    if max_abs >= 1e4:
        return 1e4, "万元"
    return 1.0, ""


_PALETTE = [
    "#2B5BA8", "#E68A2E", "#3C9B83", "#C74A53", "#7A6BC0",
    "#D17A3F", "#2F878A", "#B75AA0", "#8F9A3A", "#4B5EB2",
]
_ACCENT = "#1F3A6E"        # deep navy
_ACCENT_LIGHT = "#A4B9DE"  # light navy for area fills
_POS_COLOR = "#2F8F6A"     # deeper green
_NEG_COLOR = "#B83A45"     # deeper red
_GRID_COLOR = "#E8ECF4"
_TEXT_COLOR = "#1F2A44"
_SUBTLE_TEXT = "#5B6B85"


def _humanize_title(raw: str) -> str:
    """Turn a raw user question into a concise chart title.

    Purely heuristic — strips trailing interrogative particles, common
    command fragments (『做可视化绘图』『画图』『用图表』), and extra
    whitespace. Keeps subject/metric/period. Deterministic so batch runs
    reproduce.
    """
    s = re.sub(r"\s+", "", raw or "")
    # Drop common command tails / question particles
    for tail in ("是什么样的", "请做可视化绘图", "做可视化绘图", "做可视化",
                 "请绘制", "请绘图", "请画图", "画个图", "画图",
                 "请用图表展示", "用图表展示", "用图展示", "用图",
                 "是怎样的", "是什么", "如何", "请问", "请告诉我", "请列出"):
        if s.endswith(tail):
            s = s[: -len(tail)]
    # Drop trailing 。 ？ ? ! ！
    s = re.sub(r"[。？?！!，,、：:；;\s]+$", "", s)
    if not s:
        s = raw
    return s


def _fit_title(ax, text: str, max_width_ratio: float = 0.94, initial_fontsize: float = 14.5,
               min_fontsize: float = 9.0, color=None, pad: int = 18) -> None:
    """Set the Axes title with auto-shrink font so it fits in the figure width.

    Tries initial_fontsize first; if the rendered text width exceeds
    ``max_width_ratio`` of the figure width, reduces fontsize until it fits
    or hits ``min_fontsize``. No '…' truncation.
    """
    if color is None:
        color = _TEXT_COLOR
    fig = getattr(ax, "figure", None)
    if not hasattr(ax, "set_title") or fig is None:
        try:
            ax.set_title(text, fontsize=initial_fontsize, fontweight="bold",
                         color=color, pad=pad, loc="left")
        except Exception:
            pass
        return
    size = initial_fontsize
    while size >= min_fontsize:
        ax.set_title(text, fontsize=size, fontweight="bold", color=color,
                     pad=pad, loc="left")
        try:
            fig.canvas.draw()
            title_artist = ax.title
            bbox = title_artist.get_window_extent(fig.canvas.get_renderer())
            fig_width_px = fig.get_figwidth() * fig.dpi
            if bbox.width <= fig_width_px * max_width_ratio:
                return
        except Exception:
            # Can't measure (headless / test mocks) — accept current size
            return
        size -= 0.5
    # Leave at min size if still too long; at this point it's readable.


def _apply_common_style(ax, chart_type: str) -> None:
    # Polished editorial look: thinner spines, muted grid, quiet tick style.
    # Each call is guarded against missing methods so the minimal test mocks
    # (see tests/test_chart.py::FakeAxes) continue to work.
    try:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(_GRID_COLOR)
        ax.spines["left"].set_linewidth(0.8)
        ax.spines["bottom"].set_color(_GRID_COLOR)
        ax.spines["bottom"].set_linewidth(0.8)
    except Exception:
        pass
    try:
        ax.tick_params(axis="both", colors=_SUBTLE_TEXT, labelsize=10, length=0)
    except TypeError:
        pass
    if chart_type != "pie" and hasattr(ax, "grid"):
        try:
            ax.grid(axis="y", color=_GRID_COLOR, linestyle="-", linewidth=0.9, alpha=1.0, zorder=0)
            ax.set_axisbelow(True)
        except Exception:
            pass


def _gradient_fill_bar(ax, bars, color: str, alpha_top: float = 1.0, alpha_bottom: float = 0.55):
    """Overlay a vertical gradient on each bar for depth.

    Uses imshow with a 2-stop linear gradient clipped to the bar's bbox."""
    import numpy as np
    from matplotlib.patches import Rectangle
    from matplotlib.colors import LinearSegmentedColormap
    try:
        cmap = LinearSegmentedColormap.from_list("grad", [
            (1.0, color),
            (0.0, color),
        ])
        for bar in bars:
            x, y = bar.get_xy()
            w, h = bar.get_width(), bar.get_height()
            # Draw a semi-transparent gradient rectangle on top of the bar.
            gradient = np.linspace(alpha_top, alpha_bottom, 100).reshape(-1, 1)
            extent = (x, x + w, y, y + h) if h >= 0 else (x, x + w, y + h, y)
            ax.imshow(
                gradient, aspect="auto", extent=extent,
                cmap=cmap, alpha=1.0, zorder=3,
                origin="lower" if h >= 0 else "upper",
                interpolation="bilinear",
            )
    except Exception:
        # Gradient is eye candy; keep base bars if anything fails.
        pass


def _safe_call(obj, attr, *args, **kwargs):
    method = getattr(obj, attr, None)
    if method is None:
        return None
    try:
        return method(*args, **kwargs)
    except Exception:
        return None


def render_chart(
    chart_type: str,
    rows: Sequence[dict],
    output_path: str,
    title: str = "",
    value_field: str | None = None,
) -> str | None:
    if chart_type == "none" or not rows:
        return None

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Drop rows whose value is effectively 0 — they clutter the chart with
    # "0.00亿元" labels when the underlying SQL returned NULL (safe_chart_data
    # coerces NULL/missing fields to 0.0). Keep at least one row so the
    # render doesn't error on empty input.
    filtered = [(str(row.get("label", idx)), float(row.get("value", 0) or 0))
                for idx, row in enumerate(rows, start=1)]
    kept = [(l, v) for (l, v) in filtered if abs(v) >= 1e-6]
    if not kept:
        kept = filtered[:1]
    labels = [l for (l, _) in kept]
    raw_values = [v for (_, v) in kept]

    base_unit = _FIELD_UNITS.get(value_field or "", "")
    divisor, unit_label = _detect_unit_scale(raw_values, base_unit)
    values = [v / divisor for v in raw_values]

    # Dynamic figure size: wider (& taller for >20) when there are many bars
    # so labels have room to breathe. Keep a floor of 9 inches.
    n = len(labels)
    if chart_type == "bar" and n > 15:
        fig_w = min(18, max(9, 9 + (n - 15) * 0.45))
        fig_h = 6.2
    else:
        fig_w, fig_h = 9, 5.4
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    # Best-effort — tests mock subplots with a minimal fake object.
    if hasattr(fig, "set_facecolor"):
        fig.set_facecolor("white")
    if hasattr(ax, "set_facecolor"):
        ax.set_facecolor("#FBFBFB")

    if chart_type == "line":
        ax.plot(
            labels, values,
            color=_ACCENT, linewidth=2.8,
            marker="o", markersize=9, markerfacecolor="white",
            markeredgecolor=_ACCENT, markeredgewidth=2.4,
            zorder=3, solid_capstyle="round",
        )
        # Gradient-ish area under curve
        _safe_call(ax, "fill_between", range(len(labels)), values, 0, color=_ACCENT, alpha=0.12, zorder=2)
        # Zero reference if data crosses zero
        if min(values) < 0 < max(values):
            _safe_call(ax, "axhline", 0, color=_SUBTLE_TEXT, linewidth=1.0, linestyle="-", alpha=0.35, zorder=1)
        if hasattr(ax, "annotate"):
            for i, v in enumerate(values):
                ax.annotate(
                    f"{v:,.2f}{unit_label}",
                    (i, v),
                    textcoords="offset points", xytext=(0, 14),
                    ha="center", fontsize=9.5, color=_TEXT_COLOR, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.32", facecolor="white",
                              edgecolor=_ACCENT_LIGHT, linewidth=0.8, alpha=0.95),
                )
        else:
            for i, v in enumerate(values):
                _safe_call(ax, "text", i, v, f"{v:,.2f}{unit_label}")
        _safe_call(ax, "margins", x=0.06, y=0.22)
    elif chart_type == "pie":
        colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(labels))]
        wedges, texts, autotexts = ax.pie(
            raw_values,
            labels=labels,
            autopct=lambda pct: f"{pct:.1f}%" if pct > 3 else "",
            startangle=90,
            colors=colors,
            wedgeprops=dict(edgecolor="white", linewidth=1.5),
            textprops=dict(fontsize=10, color="#333"),
        )
        for at in autotexts:
            at.set_color("white")
            at.set_fontweight("bold")
        _safe_call(ax, "axis", "equal")
    else:  # bar
        # Color bars: +/- distinct for signed data; mostly a single accent so
        # the chart reads as "one story" rather than a rainbow.
        has_sign = any(v < 0 for v in values)
        if has_sign:
            colors = [_POS_COLOR if v >= 0 else _NEG_COLOR for v in values]
        elif len(values) <= 2:
            # For true comparison (2 bars) use primary + secondary accent
            colors = [_ACCENT, _PALETTE[1]]
        else:
            # 3+ bars: mostly the primary accent, so the data stands out —
            # variation from gradient + spacing rather than rainbow colors.
            colors = [_ACCENT] * len(values)
        # Bar width + label strategy scales with density:
        #   ≤12: full width, always show value labels
        #   13-20: thinner bars, label every bar but smaller font
        #   >20: narrow bars, label only top/bottom outliers + every 3rd bar
        n = len(labels)
        if n <= 12:
            bar_width = 0.58
            label_fontsize = 10
            show_label_on = lambda _i, _v, _maxv: True  # noqa: E731
        elif n <= 20:
            bar_width = 0.74
            label_fontsize = 8.5
            show_label_on = lambda _i, _v, _maxv: True  # noqa: E731
        else:
            bar_width = 0.82
            label_fontsize = 8
            # Rank by magnitude; label top 5 + bottom 5 + every 4th bar
            order = sorted(range(n), key=lambda i: -abs(values[i]))
            label_set = set(order[:5]) | set(order[-5:]) | {i for i in range(n) if i % 4 == 0}
            show_label_on = lambda i, _v, _maxv: i in label_set  # noqa: E731
        try:
            bars = ax.bar(labels, values, color=colors,
                          edgecolor="white", linewidth=0.8 if n > 15 else 1.2,
                          width=bar_width, zorder=3)
        except TypeError:
            bars = ax.bar(labels, values, color=colors[0] if colors else _ACCENT)
        # Thin lighter cap at the top of each bar — gives subtle depth
        # without overwhelming the color. Skipped for signed bars where the
        # cap could confuse the sign direction, and for dense bars where the
        # cap adds visual noise instead of depth.
        try:
            if not has_sign and n <= 15:
                from matplotlib.colors import to_rgb
                for bar, c in zip(bars, colors):
                    h = bar.get_height()
                    if h <= 0:
                        continue
                    rgb = to_rgb(c)
                    rgb_light = tuple(min(1.0, ch * 1.3 + 0.08) for ch in rgb)
                    cap_height = h * 0.035
                    ax.bar(
                        bar.get_x() + bar.get_width() / 2,
                        cap_height,
                        width=bar.get_width(), bottom=h - cap_height,
                        color=rgb_light, edgecolor="none", zorder=3.5,
                        align="center",
                    )
        except Exception:
            pass
        spread = (max(values) - min(values)) or abs(max(values, key=abs)) or 1
        for i, (bar, v) in enumerate(zip(bars, values)):
            if not show_label_on(i, v, max(abs(x) for x in values) or 1):
                continue
            y_text = bar.get_height()
            va = "bottom" if y_text >= 0 else "top"
            offset = 0.015 * spread
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                y_text + (offset if y_text >= 0 else -offset),
                f"{v:,.2f}{unit_label}",
                ha="center", va=va, fontsize=label_fontsize, color=_TEXT_COLOR,
                fontweight="bold", zorder=5,
            )
        if has_sign:
            _safe_call(ax, "axhline", 0, color=_SUBTLE_TEXT, linewidth=0.9, alpha=0.5)

    _apply_common_style(ax, chart_type)
    _fit_title(ax, _humanize_title(title))
    if chart_type != "pie":
        # Rotate long labels for readability
        try:
            if max(len(s) for s in labels) > 6:
                ax.tick_params(axis="x", rotation=22)
                plt.setp(ax.get_xticklabels(), ha="right")
        except Exception:
            pass
        ylabel_text = f"单位：{unit_label}" if unit_label else ("单位：%" if value_field and "ratio" in (value_field or "") else "")
        if ylabel_text:
            ax.set_ylabel(ylabel_text, fontsize=10, color=_SUBTLE_TEXT, labelpad=8)

    fig.tight_layout()
    try:
        fig.savefig(path, format="jpg", dpi=150, facecolor="white", bbox_inches="tight")
    except TypeError:
        # Tests pass a minimal FakeFigure.savefig(path, format, dpi).
        fig.savefig(path, format="jpg", dpi=150)
    plt.close(fig)
    return str(path)
