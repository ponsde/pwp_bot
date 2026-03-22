import json
from pathlib import Path

from pipeline import ensure_demo_db, run_answer


def test_pipeline_answer_end_to_end(tmp_path: Path):
    db_path = tmp_path / "finance.db"
    ensure_demo_db(str(db_path))
    input_path = tmp_path / "questions.json"
    input_path.write_text(json.dumps([
        {"Q": "金花股份利润总额是多少"},
        {"Q": "2025年第三季度的"}
    ], ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "result_2.xlsx"
    run_answer(str(input_path), str(db_path), str(output))
    assert output.exists()
