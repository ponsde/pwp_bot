"""Pipeline entrypoint for ETL and answer tasks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import REPORTS_DIR
from src.etl.loader import ETLLoader
from src.query.answer import build_answer_content, build_answer_record, write_result_xlsx
from src.query.chart import render_chart, select_chart_type
from src.query.conversation import ConversationManager
from src.query.text2sql import Text2SQLEngine


def run_etl(input_dir: str, db_path: str) -> dict[str, object]:
    loader = ETLLoader(Path(db_path))
    pdf_paths = sorted(Path(input_dir).rglob("*.pdf"))
    results = [loader.load_pdf(pdf_path) for pdf_path in pdf_paths]
    summary = {
        "status": "completed",
        "db_path": db_path,
        "input_dir": input_dir,
        "processed": len(results),
        "loaded": sum(1 for item in results if item["status"] == "loaded"),
        "skipped": sum(1 for item in results if item["status"] == "skipped"),
        "rejected": sum(1 for item in results if item["status"] == "rejected"),
        "results": results,
    }
    return summary


def run_answer(input_path: str, db_path: str, output_xlsx: str) -> str:
    engine = Text2SQLEngine(db_path=db_path)
    records = []
    sql_map = {}
    questions = json.loads(Path(input_path).read_text(encoding="utf-8"))
    conversation = ConversationManager()
    for item in questions:
        question = item["Q"]
        conversation.add_user_message(question)
        result = engine.query(question, conversation)
        if result.needs_clarification:
            content = result.clarification_question or "请补充信息。"
            images = []
        elif result.error:
            content = result.error
            images = []
        else:
            chart_type = select_chart_type(question, [{"label": k, "value": v} for row in result.rows for k, v in row.items()])
            image = render_chart(chart_type, [{"label": str(i+1), "value": next(iter(row.values()))} for i, row in enumerate(result.rows)], f"result/B{len(records)+1:04d}_1.jpg", question)
            images = [image] if image else []
            content = build_answer_content(question, result.rows)
            sql_map[question] = result.sql or ""
        conversation.add_assistant_message(content)
        records.append(build_answer_record(question, content, images))
    return write_result_xlsx(records, output_xlsx, sql_map)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["etl", "answer"], required=True)
    parser.add_argument("--db-path", default="data/db/finance.db")
    parser.add_argument("--input", default=str(REPORTS_DIR))
    parser.add_argument("--output", default="result_2.xlsx")
    args = parser.parse_args()

    Path(args.db_path).parent.mkdir(parents=True, exist_ok=True)
    if args.task == "etl":
        print(json.dumps(run_etl(args.input, args.db_path), ensure_ascii=False, indent=2))
    else:
        print(run_answer(args.input, args.db_path, args.output))


if __name__ == "__main__":
    main()
