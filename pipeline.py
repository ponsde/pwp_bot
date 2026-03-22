"""Pipeline entrypoint for ETL and answer tasks."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from src.query.answer import build_answer_content, build_answer_record, write_result_xlsx
from src.query.chart import render_chart, select_chart_type
from src.query.conversation import ConversationManager
from src.query.text2sql import CREATE_TABLE_SQL, Text2SQLEngine


def ensure_demo_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(CREATE_TABLE_SQL)
        conn.execute(
            "INSERT OR REPLACE INTO income_sheet VALUES (1,'600080','金花股份','2025Q3',2025,123000000,31400000,25100000)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO income_sheet VALUES (2,'000999','华润三九','2025Q3',2025,456000000,88000000,70000000)"
        )
        conn.commit()
    finally:
        conn.close()


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
    parser.add_argument("--input", default="questions.json")
    parser.add_argument("--output", default="result_2.xlsx")
    args = parser.parse_args()

    Path(args.db_path).parent.mkdir(parents=True, exist_ok=True)
    if args.task == "etl":
        ensure_demo_db(args.db_path)
        print(args.db_path)
    else:
        ensure_demo_db(args.db_path)
        print(run_answer(args.input, args.db_path, args.output))


if __name__ == "__main__":
    main()
