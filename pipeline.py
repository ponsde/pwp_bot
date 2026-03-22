"""Pipeline entrypoint for ETL and answer tasks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import openpyxl

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
    return {
        "status": "completed",
        "db_path": db_path,
        "input_dir": input_dir,
        "processed": len(results),
        "loaded": sum(1 for r in results if r["status"] == "loaded"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "rejected": sum(1 for r in results if r["status"] == "rejected"),
        "results": results,
    }


def _load_questions_xlsx(path: str) -> list[dict]:
    """Read questions xlsx (附件4 format): columns 编号, 问题类型, 问题."""
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()
    questions = []
    for row in rows:
        if not row or not row[0]:
            continue
        question_id = str(row[0]).strip()
        question_json = str(row[2]).strip() if row[2] else "[]"
        turns = json.loads(question_json)
        questions.append({"id": question_id, "turns": turns})
    return questions


def run_answer(questions_path: str, db_path: str, output_xlsx: str) -> str:
    engine = Text2SQLEngine(db_path=db_path)
    all_records: list[dict] = []
    all_sql: dict[str, str] = {}

    questions = _load_questions_xlsx(questions_path)
    for q_item in questions:
        question_id = q_item["id"]
        turns = q_item["turns"]
        conversation = ConversationManager()
        turn_records: list[dict] = []

        for turn in turns:
            question = turn["Q"]
            conversation.add_user_message(question)
            result = engine.query(question, conversation)

            if result.needs_clarification:
                content = result.clarification_question or "请补充信息。"
                chart_type_str = "none"
                images: list[str] = []
            elif result.error:
                content = result.error
                chart_type_str = "none"
                images = []
            else:
                chart_type_str = select_chart_type(
                    question,
                    [{"label": k, "value": v} for row in result.rows for k, v in row.items()],
                )
                image = render_chart(
                    chart_type_str,
                    [{"label": str(i + 1), "value": next(iter(row.values()))} for i, row in enumerate(result.rows)],
                    f"result/{question_id}_{len(turn_records) + 1}.jpg",
                    question,
                )
                images = [image] if image else []
                content = build_answer_content(question, result.rows)
                all_sql[question] = result.sql or ""

            conversation.add_assistant_message(content)
            turn_records.append(build_answer_record(question, content, images, chart_type_str))

        all_records.append({
            "id": question_id,
            "turns_input": turns,
            "turn_records": turn_records,
        })

    return _write_grouped_result_xlsx(all_records, output_xlsx, all_sql)


def _write_grouped_result_xlsx(
    grouped: list[dict], output_path: str, sql_map: dict[str, str]
) -> str:
    """Write result_2.xlsx in 附件7 format: one row per question group."""
    import pandas as pd

    rows = []
    for item in grouped:
        question_id = item["id"]
        turns_input = item["turns_input"]
        turn_records = item["turn_records"]
        first_sql = ""
        chart_type_label = "无"
        for rec in turn_records:
            q = rec["Q"]
            if q in sql_map and sql_map[q]:
                first_sql = sql_map[q]
            if rec.get("chart_type", "无") != "无":
                chart_type_label = rec["chart_type"]
        answer_json = json.dumps(
            [{"Q": rec["Q"], "A": rec["A"]} for rec in turn_records],
            ensure_ascii=False,
        )
        rows.append({
            "编号": question_id,
            "问题": json.dumps(turns_input, ensure_ascii=False),
            "SQL查询语句": first_sql,
            "图形格式": chart_type_label,
            "回答": answer_json,
        })
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False)
    return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Financial Report QA Pipeline")
    parser.add_argument("--task", choices=["etl", "answer"], required=True)
    parser.add_argument("--db-path", default="data/db/finance.db")
    parser.add_argument("--input", default=str(REPORTS_DIR), help="PDF directory for ETL")
    parser.add_argument("--questions", default=None, help="Questions xlsx for answer task")
    parser.add_argument("--output", default="result_2.xlsx")
    args = parser.parse_args()

    Path(args.db_path).parent.mkdir(parents=True, exist_ok=True)
    if args.task == "etl":
        print(json.dumps(run_etl(args.input, args.db_path), ensure_ascii=False, indent=2))
    else:
        if not args.questions:
            raise SystemExit("--questions is required for answer task")
        print(run_answer(args.questions, args.db_path, args.output))


if __name__ == "__main__":
    main()
