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


def _safe_chart_data(rows: list[dict]) -> tuple[list[dict], str | None]:
    """Build chart-friendly data — delegates to shared chart utility."""
    from src.query.chart import safe_chart_data
    return safe_chart_data(rows)


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
        content = build_answer_content(question, result.rows, intent=result.intent)
        sql_text = result.sql or ""
        chart_data, chart_vf = _safe_chart_data(result.rows)
        chart_type = select_chart_type(question, chart_data)
        image = render_chart(chart_type, chart_data, "result/gradio_preview.jpg", question, value_field=chart_vf) if chart_data else None
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
