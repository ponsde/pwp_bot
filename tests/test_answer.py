from pathlib import Path

import pandas as pd

from pipeline import _safe_chart_data as pipeline_safe_chart_data
from src.query.answer import build_answer_content, build_answer_record, write_result_xlsx
from src.query.chart import safe_chart_data


def test_answer_format_and_xlsx(tmp_path: Path):
    content = build_answer_content("利润总额是多少", [{"total_profit": 3140}])
    assert "利润总额3,140.00万元。" == content
    record = build_answer_record("利润总额是多少", content, ["result/a.jpg"], chart_type="bar")
    output = tmp_path / "result_2.xlsx"
    write_result_xlsx([record], str(output), {"利润总额是多少": "SELECT 1"})
    df = pd.read_excel(output)
    assert df.loc[0, "SQL查询语句"] == "SELECT 1"
    assert df.loc[0, "图形格式"] == "柱状图"


def test_build_answer_content_keeps_company_and_period_identifiers():
    rows = [
        {"stock_abbr": "金花股份", "report_period": "2022FY", "total_operating_revenue": 56500},
        {"stock_abbr": "华润三九", "report_period": "2024Q3", "total_operating_revenue": 2473900},
    ]

    content = build_answer_content("对比两家公司营收", rows)

    assert "金花股份" in content
    assert "华润三九" in content
    assert "2022年" in content
    assert "2024年第三季度" in content
    assert "2022FY" not in content
    assert "2024Q3" not in content
    assert "5.65亿元" in content
    assert "247.39亿元" in content
    # Field names should be Chinese labels, not raw DB column names
    assert "total_operating_revenue" not in content


def test_build_answer_content_formats_yoy_growth_naturally():
    rows = [{
        "stock_abbr": "华润三九",
        "report_period": "2024FY",
        "current_value": 400000000,
        "previous_value": 350000000,
        "yoy_ratio": 0.1429,
    }]
    content = build_answer_content("华润三九2024年净利润同比是多少", rows, intent={"fields": ["net_profit"]})
    assert "同比增长14.29%" in content
    assert "净利润" in content
    assert "本期40,000.00万元" in content
    assert "上期35,000.00万元" in content


def test_build_answer_content_formats_yoy_decline_and_none():
    decline = build_answer_content(
        "同比",
        [{
            "stock_abbr": "金花股份",
            "report_period": "2024FY",
            "current_value": 8500,
            "previous_value": 10000,
            "yoy_ratio": -0.15,
        }],
        intent={"fields": ["net_profit"]},
    )
    none_case = build_answer_content(
        "同比",
        [{
            "stock_abbr": "金花股份",
            "report_period": "2024FY",
            "current_value": 4000,
            "previous_value": 0,
            "yoy_ratio": None,
        }],
        intent={"fields": ["net_profit"]},
    )
    assert "同比下降15.00%" in decline
    assert "无法计算同比（上期值为零）" in none_case


def test_build_answer_content_single_value_does_not_echo_question_text():
    question = "在这些企业中利润最高的是哪家"
    content = build_answer_content(question, [{"total_profit": 50000.00}])

    assert content == "利润总额5.00亿元。"
    assert question not in content


def test_build_answer_content_single_value_formats_yoy_field_naturally():
    question = "在这些企业中年同比上涨幅度最大的是哪家企业"
    content = build_answer_content(question, [{"net_profit_yoy_growth": 271.60}])

    assert content == "净利润同比增长271.60%。"
    assert question not in content


def test_build_answer_content_single_value_falls_back_to_raw_field_name_when_label_missing():
    content = build_answer_content("任意问题", [{"unknown_metric": 12.5}])

    assert content == "unknown_metric12.50。"


def test_safe_chart_data_picks_numeric_value_from_multi_column_rows():
    rows = [
        {
            "stock_abbr": "金花股份",
            "report_period": "2024FY",
            "current_value": 400000000,
            "previous_value": 350000000,
            "yoy_ratio": 0.1429,
        }
    ]
    chart_data = safe_chart_data(rows)
    pipeline_chart = pipeline_safe_chart_data(rows)
    assert chart_data == [{"label": "金花股份", "value": 0.1429}]
    assert pipeline_chart == chart_data
