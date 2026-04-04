from pathlib import Path

from src.query import chart as chart_module
from src.query.chart import render_chart, select_chart_type


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
