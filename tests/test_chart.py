from pathlib import Path

from src.query import chart as chart_module
from src.query.chart import render_chart, safe_chart_data, select_chart_type, pick_chart_columns


def test_select_chart_type_rules(tmp_path: Path):
    assert select_chart_type("近三年净利润趋势", [{"value": 1}, {"value": 2}]) == "line"
    assert select_chart_type("营收占比", [{"value": 1}, {"value": 2}]) == "pie"
    assert select_chart_type("对比两家公司营收", [{"value": 1}, {"value": 2}]) == "bar"
    assert select_chart_type("请做可视化绘图", [{"value": 1}, {"value": 2}]) == "bar"
    assert select_chart_type("请帮我可视化展示", [{"value": 1}, {"value": 2}]) == "bar"
    assert select_chart_type("请画图", [{"value": 1}, {"value": 2}]) == "bar"
    assert select_chart_type("生成图表", [{"value": 1}, {"value": 2}]) == "bar"
    assert select_chart_type("2025年第三季度的", [{"value": 1}]) == "none"
    output = tmp_path / "chart.jpg"
    path = render_chart("bar", [{"label": "A", "value": 1}], str(output), "test")
    assert path == str(output)
    assert output.exists()


def test_configure_cjk_font_prefers_named_system_font(monkeypatch):
    monkeypatch.setattr(chart_module.font_manager, "findfont", lambda *args, **kwargs: "/fonts/SimHei.ttf")

    selected = chart_module._configure_cjk_font()

    assert selected == chart_module._FONT_CANDIDATES[0]
    assert chart_module.plt.rcParams["font.sans-serif"][0] == chart_module._FONT_CANDIDATES[0]
    assert chart_module.plt.rcParams["axes.unicode_minus"] is False


def test_configure_cjk_font_falls_back_to_known_system_path(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(chart_module.font_manager, "findfont", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("missing")))
    fallback_path = tmp_path / "wqy-microhei.ttc"
    fallback_path.write_text("fake-font", encoding="utf-8")

    class FakeFontProperties:
        def __init__(self, fname):
            self.fname = fname

        def get_name(self):
            return "WenQuanYi Micro Hei"

    monkeypatch.setattr(chart_module.font_manager, "FontProperties", FakeFontProperties)

    selected = chart_module._configure_cjk_font(fallback_path)

    assert selected == str(fallback_path)
    assert chart_module.plt.rcParams["font.sans-serif"][0] == "WenQuanYi Micro Hei"
    assert chart_module.plt.rcParams["axes.unicode_minus"] is False


def test_configure_cjk_font_logs_warning_when_no_font_available(monkeypatch, caplog, tmp_path: Path):
    monkeypatch.setattr(chart_module.font_manager, "findfont", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("missing")))
    fallback_path = tmp_path / "missing-font.ttc"

    with caplog.at_level("WARNING"):
        selected = chart_module._configure_cjk_font(fallback_path)

    assert selected is None
    assert "No CJK font found" in caplog.text


def test_safe_chart_data_formats_report_period_labels():
    rows = [{"report_period": "2022FY", "total_operating_revenue": 56500}]

    chart_data, value_field = safe_chart_data(rows)

    assert chart_data == [{"label": "2022年", "value": 56500.0}]
    assert value_field == "total_operating_revenue"


def test_pick_chart_columns_formats_report_period_label_when_used_as_axis_field():
    label, value, label_field, value_field = pick_chart_columns({"report_period": "2024Q3", "total_profit": 3140})

    assert label == "2024年第三季度"
    assert value == 3140
    assert label_field == "report_period"


def test_render_chart_annotations_include_unit_suffix(monkeypatch, tmp_path: Path):
    output = tmp_path / "chart.jpg"
    annotations: list[str] = []

    class FakeAxes:
        def plot(self, *args, **kwargs):
            return None

        def annotate(self, text, *args, **kwargs):
            annotations.append(text)

        def pie(self, *args, **kwargs):
            return None

        def bar(self, labels, values, color=None):
            class FakeBar:
                def __init__(self, x, height):
                    self._x = x
                    self._height = height

                def get_x(self):
                    return self._x

                def get_width(self):
                    return 1.0

                def get_height(self):
                    return self._height

            return [FakeBar(idx, value) for idx, value in enumerate(values)]

        def text(self, x, y, text, **kwargs):
            annotations.append(text)

        def set_title(self, *args, **kwargs):
            return None

        def tick_params(self, *args, **kwargs):
            return None

        def set_ylabel(self, *args, **kwargs):
            return None

    class FakeFigure:
        def tight_layout(self):
            return None

        def savefig(self, path, format=None, dpi=None):
            Path(path).write_bytes(b"fake")

    monkeypatch.setattr(chart_module.plt, "subplots", lambda figsize=None: (FakeFigure(), FakeAxes()))
    monkeypatch.setattr(chart_module.plt, "close", lambda fig: None)

    line_path = render_chart("line", [{"label": "2022年", "value": 47_901_000}], str(output), "test")
    bar_path = render_chart("bar", [{"label": "2022年", "value": 4_594_000_000}], str(output), "test")

    assert line_path == str(output)
    assert bar_path == str(output)
    assert "4,790.10万元" in annotations
    assert "45.94亿元" in annotations
