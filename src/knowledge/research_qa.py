"""Research QA orchestration for SQL/RAG/Hybrid tasks."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from src.knowledge.retriever import ResearchRetriever, RetrievalItem
from src.llm.client import LLMClient
from src.query.answer import build_answer_content
from src.query.chart import select_chart_type
from src.query.conversation import ConversationManager
from src.query.text2sql import QueryResult, Text2SQLEngine


@dataclass(frozen=True)
class ResearchReference:
    paper_path: str
    text: str
    paper_image: str = ""


@dataclass(frozen=True)
class ResearchAnswer:
    question: str
    route: str
    answer: str
    sql: str
    chart_type: str
    references: list[ResearchReference]


class ResearchQAEngine:
    def __init__(self, db_path: str, client: Any, llm_client: LLMClient | None = None, retriever: ResearchRetriever | None = None):
        self.db_path = db_path
        self.client = client
        self.llm_client = llm_client
        self.retriever = retriever or ResearchRetriever(client)
        self.sql_engine = Text2SQLEngine(db_path=db_path, llm_client=llm_client)

    def classify_intent(self, question: str) -> str:
        text = question.strip()
        if self.llm_client:
            prompt = '请判断问题属于 sql、rag 或 hybrid，只返回JSON，如{"route":"sql"}。\n问题：' + text
            try:
                result = self.llm_client.complete(prompt, json_mode=True)
                route = str(result.get("route", "")).strip().lower() if isinstance(result, dict) else ""
                if route in {"sql", "rag", "hybrid"}:
                    return route
            except Exception:
                pass
        has_reason = any(token in text for token in ["原因", "为什么"])
        has_research = any(token in text for token in ["医保目录", "谈判", "新增的中药产品", "研报"])
        has_finance = any(token in text for token in ["收入", "利润", "可视化", "近三年"])
        if has_reason:
            return "hybrid"
        if has_research:
            return "rag"
        if has_finance:
            return "sql"
        return "rag"

    def split_multi_intent(self, question: str, conversation: ConversationManager | None = None) -> list[str]:
        text = question.strip()
        if self.llm_client:
            prompt = (
                "请将下面的复合问题拆成按顺序回答的子问题列表，只返回 JSON，格式如"
                '{"questions": ["子问题1", "子问题2"]}。若无需拆分，返回原问题单元素列表。\n'
                f"问题：{text}"
            )
            if conversation and conversation.history:
                prompt += f"\n上下文：\n{conversation.render()}"
            try:
                result = self.llm_client.complete(prompt, json_mode=True)
                if isinstance(result, dict):
                    questions = result.get("questions", [])
                    if isinstance(questions, list):
                        cleaned = [str(item).strip() for item in questions if str(item).strip()]
                        if cleaned:
                            return cleaned
            except Exception:
                pass
        return self._heuristic_split_multi_intent(text)

    def answer_question(self, question: str, conversation: ConversationManager | None = None) -> ResearchAnswer:
        route = self.classify_intent(question)
        if route == "sql":
            return self._answer_sql(question, conversation)
        if route == "rag":
            return self._answer_rag(question)
        return self._answer_hybrid(question, conversation)

    def _answer_sql(self, question: str, conversation: ConversationManager | None = None) -> ResearchAnswer:
        sub_questions = self.split_multi_intent(question, conversation)
        sql_parts: list[str] = []
        answer_parts: list[str] = []
        chart_rows: list[dict[str, Any]] = []
        manager = conversation or ConversationManager()
        for sub_question in sub_questions:
            result = self.sql_engine.query(sub_question, manager)
            if result.sql:
                sql_parts.append(result.sql)
            answer_parts.append(self._format_sql_result(sub_question, result))
            if result.rows and not chart_rows:
                chart_rows = result.rows
        return ResearchAnswer(
            question=question,
            route="sql",
            answer="\n".join(answer_parts),
            sql="\n\n".join(sql_parts),
            chart_type=self._select_chart_type(question, chart_rows),
            references=[],
        )

    def _answer_rag(self, question: str) -> ResearchAnswer:
        items = self.retriever.search(question, top_k=5)
        references = [ResearchReference(paper_path=item.paper_path, text=item.text) for item in items]
        return ResearchAnswer(
            question=question,
            route="rag",
            answer=self._compose_rag_answer(question, items),
            sql="",
            chart_type=self._select_chart_type(question, []),
            references=references,
        )

    def _answer_hybrid(self, question: str, conversation: ConversationManager | None = None) -> ResearchAnswer:
        manager = conversation or ConversationManager()
        data_question = self._extract_sql_subquestion(question)
        sql_result = self.sql_engine.query(data_question, manager)
        sql_answer = self._format_sql_result(data_question, sql_result)
        rag_query = self._build_hybrid_rag_query(question, data_question, sql_result)
        rag_items = self.retriever.search(rag_query, top_k=5)
        rag_answer = self._compose_rag_answer(question, rag_items)
        references = [ResearchReference(paper_path=item.paper_path, text=item.text) for item in rag_items]
        answer = f"{sql_answer}\n{rag_answer}".strip()
        return ResearchAnswer(
            question=question,
            route="hybrid",
            answer=answer,
            sql=sql_result.sql or "",
            chart_type=self._select_chart_type(question, sql_result.rows),
            references=references,
        )

    def _compose_rag_answer(self, question: str, items: list[RetrievalItem]) -> str:
        if not items:
            return "未检索到相关研报内容。"
        context = "\n\n".join(f"来源：{item.paper_path}\n内容：{item.text}" for item in items[:3])
        if self.llm_client:
            prompt = f"请基于以下研报摘录回答问题，回答简洁，并优先引用明确事实。\n问题：{question}\n\n研报摘录：\n{context}"
            try:
                return str(self.llm_client.complete(prompt)).strip()
            except Exception:
                pass
        return "\n".join(f"根据研报《{item.paper_path.split('/')[-1]}》：{item.text}" for item in items[:3] if item.text)

    def _format_sql_result(self, question: str, result: QueryResult) -> str:
        if result.needs_clarification:
            return result.clarification_question or "请补充信息。"
        if result.error:
            return result.error
        content = build_answer_content(question, result.rows)
        if result.warning:
            content += f"\n（注：{result.warning}）"
        return content

    def _heuristic_split_multi_intent(self, question: str) -> list[str]:
        normalized = question.strip()
        if not normalized:
            return []
        segments = [seg.strip() for seg in re.split(r"[？?]", normalized) if seg.strip()]
        if len(segments) <= 1:
            segments = [seg.strip() for seg in re.split(r"[；;。]", normalized.rstrip("。")) if seg.strip()]
        if len(segments) <= 1:
            return [question]

        results: list[str] = []
        carry_context = ""
        for index, segment in enumerate(segments):
            current = segment
            if index == 0:
                current = current.rstrip("，,；;") + "？"
                carry_context = self._extract_subject_context(segment)
                results.append(current)
                continue
            if carry_context and self._needs_context_inheritance(segment):
                current = f"{carry_context}{segment}"
            current = current.rstrip("，,；;") + "？"
            results.append(current)
        return results or [question]

    def _extract_subject_context(self, text: str) -> str:
        match = re.search(r"(.+?(?:是哪些|有哪些|有哪几家企业|是哪几家企业))", text)
        if match:
            return match.group(1).strip()
        if "是哪些" in text:
            return text.split("是哪些", 1)[0].strip()
        return ""

    def _needs_context_inheritance(self, text: str) -> bool:
        return text.startswith("这些") or text.startswith("其") or text.startswith("它们") or text.startswith("上述")

    def _extract_sql_subquestion(self, question: str) -> str:
        text = question.strip()
        if self.llm_client:
            prompt = (
                "请从下面问题中提取可以用财务数据库 SQL 查询的数据子问题，只返回 JSON，格式如"
                '{"sql_question": "..."}。如果原问题本身可 SQL 查询，也返回原问题；不要包含“原因/为什么”等归因表述。\n'
                f"问题：{text}"
            )
            try:
                result = self.llm_client.complete(prompt, json_mode=True)
                if isinstance(result, dict):
                    sql_question = str(result.get("sql_question", "")).strip()
                    if sql_question:
                        return sql_question
            except Exception:
                pass
        stripped = re.split(r"原因是什么|原因是啥|为什么", text, maxsplit=1)[0].strip("，,；;：: ")
        if stripped and stripped != text:
            return stripped
        metric_match = re.search(r"(.+?(?:收入|利润|销售额|营收|净利润|主营业务收入).*)", text)
        if metric_match:
            return metric_match.group(1).strip("，,；;：: ")
        return text

    def _build_hybrid_rag_query(self, question: str, data_question: str, sql_result: QueryResult) -> str:
        if sql_result.rows:
            sample = json.dumps(sql_result.rows[:3], ensure_ascii=False)
            return f"{question}\n已查询数据问题：{data_question}\n财务结果：{sample}"
        return f"{question}\n已查询数据问题：{data_question}"

    def _select_chart_type(self, question: str, rows: list[dict[str, Any]]) -> str:
        if not any(token in question for token in ["可视化", "绘图", "图表", "画图"]):
            return "无"
        chart_type = select_chart_type(question, rows)
        return "无" if chart_type == "none" else chart_type


def format_research_answer_payload(answer: ResearchAnswer) -> str:
    return json.dumps({
        "Q": answer.question,
        "A": answer.answer,
        "references": [
            {"paper_path": ref.paper_path, "text": ref.text, "paper_image": ref.paper_image}
            for ref in answer.references
        ],
    }, ensure_ascii=False)
