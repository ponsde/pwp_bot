"""Minimal Gradio app for financial QA."""
from __future__ import annotations

from pathlib import Path

import gradio as gr

from pipeline import ensure_demo_db
from src.query.answer import build_answer_content
from src.query.chart import render_chart, select_chart_type
from src.query.conversation import ConversationManager
from src.query.text2sql import Text2SQLEngine

DB_PATH = "data/db/finance.db"
ensure_demo_db(DB_PATH)
engine = Text2SQLEngine(DB_PATH)
conversation = ConversationManager()


def chat(question: str):
    conversation.add_user_message(question)
    result = engine.query(question, conversation)
    if result.needs_clarification:
        content = result.clarification_question or "请补充信息。"
        sql = ""
        image = None
    elif result.error:
        content = result.error
        sql = result.sql or ""
        image = None
    else:
        content = build_answer_content(question, result.rows)
        sql = result.sql or ""
        chart_type = select_chart_type(question, [{"label": str(i+1), "value": next(iter(row.values()))} for i, row in enumerate(result.rows)])
        image = render_chart(chart_type, [{"label": str(i+1), "value": next(iter(row.values()))} for i, row in enumerate(result.rows)], "result/gradio_preview.jpg", question)
    conversation.add_assistant_message(content)
    return content, sql, image


with gr.Blocks() as demo:
    gr.Markdown("# 财报智能问数助手")
    question = gr.Textbox(label="问题")
    answer = gr.Textbox(label="回答")
    sql = gr.Code(label="SQL", language="sql")
    image = gr.Image(label="图表")
    btn = gr.Button("发送")
    btn.click(chat, inputs=question, outputs=[answer, sql, image])


if __name__ == "__main__":
    demo.launch()
