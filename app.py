"""Minimal Gradio app for financial QA."""
from __future__ import annotations

from pathlib import Path

import gradio as gr

from src.query.answer import build_answer_content
from src.query.chart import render_chart, select_chart_type
from src.query.conversation import ConversationManager
from src.query.text2sql import Text2SQLEngine

DB_PATH = "data/db/finance.db"
engine = Text2SQLEngine(DB_PATH)
conversation = ConversationManager()


def _safe_chart_data(rows: list[dict]) -> list[dict]:
    """Build chart-friendly data from query rows, handling non-numeric first columns."""
    data = []
    for row in rows:
        items = list(row.items())
        if len(items) >= 2:
            label = str(items[0][1])
            value = items[1][1]
        elif len(items) == 1:
            label = str(len(data) + 1)
            value = items[0][1]
        else:
            continue
        try:
            data.append({"label": label, "value": float(value)})
        except (ValueError, TypeError):
            continue
    return data


def chat(question: str):
    conversation.add_user_message(question)
    result = engine.query(question, conversation)
    if result.needs_clarification:
        content = result.clarification_question or "请补充信息。"
        sql_text = ""
        image = None
    elif result.error:
        content = result.error
        sql_text = result.sql or ""
        image = None
    else:
        content = build_answer_content(question, result.rows)
        sql_text = result.sql or ""
        chart_data = _safe_chart_data(result.rows)
        chart_type = select_chart_type(question, chart_data)
        image = render_chart(chart_type, chart_data, "result/gradio_preview.jpg", question) if chart_data else None
    conversation.add_assistant_message(content)
    return content, sql_text, image


with gr.Blocks() as demo:
    gr.Markdown("# 财报智能问数助手")
    question = gr.Textbox(label="问题")
    answer = gr.Textbox(label="回答")
    sql_display = gr.Code(label="SQL", language="sql")
    image_display = gr.Image(label="图表")
    btn = gr.Button("发送")
    btn.click(chat, inputs=question, outputs=[answer, sql_display, image_display])


if __name__ == "__main__":
    demo.launch()
