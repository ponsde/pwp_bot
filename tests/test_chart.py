from pathlib import Path

from src.query.chart import render_chart, select_chart_type


def test_select_chart_type_rules(tmp_path: Path):
    assert select_chart_type("近三年净利润趋势", [{"value": 1}, {"value": 2}]) == "line"
    assert select_chart_type("营收占比", [{"value": 1}, {"value": 2}]) == "pie"
    assert select_chart_type("对比两家公司营收", [{"value": 1}, {"value": 2}]) == "bar"
    output = tmp_path / "chart.jpg"
    path = render_chart("bar", [{"label": "A", "value": 1}], str(output), "test")
    assert path == str(output)
    assert output.exists()
