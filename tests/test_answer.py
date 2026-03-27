from pathlib import Path

import pandas as pd

from src.query.answer import build_answer_content, build_answer_record, write_result_xlsx


def test_answer_format_and_xlsx(tmp_path: Path):
    content = build_answer_content("利润总额是多少", [{"total_profit": 3140}])
    assert "3,140.00万元" in content
    record = build_answer_record("利润总额是多少", content, ["result/a.jpg"], chart_type="bar")
    output = tmp_path / "result_2.xlsx"
    write_result_xlsx([record], str(output), {"利润总额是多少": "SELECT 1"})
    df = pd.read_excel(output)
    assert df.loc[0, "SQL查询语句"] == "SELECT 1"
    assert df.loc[0, "图形格式"] == "柱状图"


def test_build_answer_content_keeps_company_and_period_identifiers():
    rows = [
        {"stock_abbr": "金花股份", "report_period": "2023FY", "total_operating_revenue": 56500},
        {"stock_abbr": "华润三九", "report_period": "2023FY", "total_operating_revenue": 2473900},
    ]

    content = build_answer_content("对比两家公司营收", rows)

    assert "金花股份" in content
    assert "华润三九" in content
    assert "2023FY" in content
    assert "5.65亿元" in content
    assert "247.39亿元" in content
    # Field names should be Chinese labels, not raw DB column names
    assert "total_operating_revenue" not in content
