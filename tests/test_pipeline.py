from pathlib import Path

from pipeline import ensure_demo_db, run_answer


def test_pipeline_answer_end_to_end(tmp_path: Path):
    db_path = tmp_path / "finance.db"
    ensure_demo_db(str(db_path))
    output = tmp_path / "result_2.xlsx"
    run_answer("data/sample/示例数据/附件4：问题汇总.xlsx", str(db_path), str(output))
    assert output.exists()
