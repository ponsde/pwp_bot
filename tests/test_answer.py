from pathlib import Path

import pandas as pd

from src.query.answer import build_answer_content, build_answer_record, write_result_xlsx


def test_answer_format_and_xlsx(tmp_path: Path):
    content = build_answer_content("利润总额是多少", [{"total_profit": 31400000}])
    assert "3140.00万元" in content
    record = build_answer_record("利润总额是多少", content, ["result/a.jpg"])
    output = tmp_path / "result_2.xlsx"
    write_result_xlsx([record], str(output), {"利润总额是多少": "SELECT 1"})
    df = pd.read_excel(output)
    assert df.loc[0, "SQL查询语句"] == "SELECT 1"
