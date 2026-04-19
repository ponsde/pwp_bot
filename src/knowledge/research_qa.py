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
    chart_rows: list[dict[str, Any]] | None = None


class ResearchQAEngine:
    def __init__(self, db_path: str, client: Any, llm_client: LLMClient | None = None, retriever: ResearchRetriever | None = None):
        self.db_path = db_path
        self.client = client
        self.llm_client = llm_client
        self.retriever = retriever or ResearchRetriever(client)
        self.sql_engine = Text2SQLEngine(db_path=db_path, llm_client=llm_client)

    _CLASSIFY_PROMPT = (
        "你是中药上市公司财报问答系统的路由分类器。\n\n"
        "数据库中有四张财务报表（利润表、资产负债表、现金流量表、核心经营指标表），"
        "包含各公司各报告期的财务数字（收入、利润、资产、负债、现金流、同比增长率等）。\n\n"
        "请判断用户的问题应该走哪条路径：\n"
        "- sql: 问题可以通过查询财务数据库直接回答（如某公司某年利润是多少、对比、排名、趋势等）\n"
        "- rag: 问题需要从研究报告/年报文本中检索（如原因分析、政策影响、产品信息、战略规划、行业趋势等）\n"
        "- hybrid: 问题同时需要财务数据和研报分析（如某指标变化的原因）\n\n"
        "判断要点：\n"
        "- 问[是多少][有哪些公司][排名][对比][趋势变化] -> sql\n"
        "- 问[为什么][原因][影响因素][产品有哪些][政策][战略] -> rag\n"
        "- 问[某指标变化/增长/下降的原因] -> hybrid（先查数据再分析原因）\n\n"
        '只返回JSON，如 {"route":"sql"}。\n'
    )

    _SPLIT_PROMPT = (
        "你是中药上市公司财报问答系统的问题拆分器。\n\n"
        "用户的问题可能包含多个子问题，请将其拆成可以独立回答的子问题列表。\n\n"
        "拆分规则：\n"
        "- 每个子问题应该能独立用一条SQL或一次检索回答\n"
        "- 保留必要的上下文（公司名、时间范围等），使每个子问题自包含\n"
        "- 如果问题问了A，然后问[其中最大/最小的是谁]，要拆成独立子问题\n"
        "- 如果问题要求对比多个指标或维度，每个指标一个子问题\n\n"
        "示例：\n"
        '输入: "2024年利润最高的top10企业是哪些？这些企业的销售额年同比是多少？'
        '年同比上涨幅度最大的是哪家企业？"\n'
        '输出: {"questions": ["2024年利润最高的top10企业是哪些", '
        '"2024年利润最高的top10企业的销售额年同比是多少", '
        '"2024年利润最高的top10企业中年同比上涨幅度最大的是哪家企业"]}\n\n'
        '只返回JSON，格式如 {"questions": ["子问题1", "子问题2"]}。'
        "若无需拆分，返回原问题单元素列表。\n"
    )

    def classify_intent(self, question: str) -> str:
        text = question.strip()
        if self.llm_client:
            prompt = self._CLASSIFY_PROMPT + f"问题：{text}"
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
            prompt = self._SPLIT_PROMPT + f"问题：{text}"
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
        seen_signatures: set[tuple[str, str]] = set()
        for sub_question in sub_questions:
            result = self.sql_engine.query(sub_question, manager)
            signature = (result.sql or "", json.dumps(result.rows, ensure_ascii=False, sort_keys=True))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            if result.sql:
                sql_parts.append(result.sql)
            answer_parts.append(self._format_sql_result(sub_question, result))
            if self._is_better_chart_result(result.rows, chart_rows):
                chart_rows = result.rows
            self._forward_result_context(sub_question, result, manager)
        return ResearchAnswer(
            question=question,
            route="sql",
            answer=self._deduplicate_answer_lines("\n".join(answer_parts)),
            sql="\n\n".join(sql_parts),
            chart_type=self._select_chart_type(question, chart_rows),
            references=[],
            chart_rows=chart_rows,
        )

    def _deduplicate_answer_lines(self, answer: str) -> str:
        if not answer:
            return answer
        deduplicated_lines: list[str] = []
        seen_lines: set[str] = set()
        prev_blank = False
        for line in answer.split("\n"):
            normalized_line = line.strip()
            if not normalized_line:
                if not prev_blank:
                    deduplicated_lines.append(line)
                prev_blank = True
                continue
            prev_blank = False
            if normalized_line in seen_lines:
                continue
            seen_lines.add(normalized_line)
            deduplicated_lines.append(line)
        return "\n".join(deduplicated_lines)

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
            chart_rows=[],
        )

    def _answer_hybrid(self, question: str, conversation: ConversationManager | None = None) -> ResearchAnswer:
        manager = conversation or ConversationManager()
        data_question = self._extract_sql_subquestion(question)
        sql_result = self.sql_engine.query(data_question, manager)
        rag_query = self._build_hybrid_rag_query(question, data_question, sql_result)
        rag_items = self.retriever.search(rag_query, top_k=5)
        references = [ResearchReference(paper_path=item.paper_path, text=item.text) for item in rag_items]

        sql_unavailable = (
            (sql_result.clarification_question or "请补充信息。") if sql_result.needs_clarification
            else sql_result.error if sql_result.error
            else None
        )
        rag_text = self._compose_rag_answer(question, rag_items)
        rag_answer = (
            f"SQL 数据暂不可用（{sql_unavailable}）。以下为基于研报的补充说明：\n{rag_text}"
            if sql_unavailable else rag_text
        )

        return ResearchAnswer(
            question=question,
            route="hybrid",
            answer=rag_answer.strip(),
            sql=sql_result.sql or "",
            chart_type=self._select_chart_type(question, sql_result.rows),
            references=references,
            chart_rows=sql_result.rows,
        )

    def _compose_rag_answer(self, question: str, items: list[RetrievalItem]) -> str:
        if not items:
            return "未检索到相关研报内容。"
        context = "\n\n".join(f"来源：{item.paper_path}\n内容：{item.text}" for item in items[:3])
        if self.llm_client:
            prompt = (
                "请基于以下研报摘录回答问题。要求：\n"
                "1. 回答简洁，优先引用明确事实\n"
                "2. 使用正式书面语，不要使用对话式口吻\n"
                "3. 不要反问用户，不要说\u201c如果你需要\u201d、\u201c我可以帮你\u201d等表述\n"
                "4. 直接给出结论性回答\n\n"
                f"问题：{question}\n\n研报摘录：\n{context}"
            )
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
        content = build_answer_content(question, result.rows, intent=result.intent)
        if self._is_superlative_question(question) and len(result.rows) == 1:
            return self._build_superlative_summary(question, result.rows[0], result.intent, content)
        return content

    def _forward_result_context(self, question: str, result: QueryResult, manager: ConversationManager) -> None:
        if not result.rows:
            return
        companies = []
        for row in result.rows:
            company = row.get("stock_abbr")
            if company:
                companies.append(str(company))
        if companies:
            manager.slots["companies"] = list(dict.fromkeys(companies))

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
        if len(rows) > 1 and any("stock_abbr" in row for row in rows):
            return "bar"
        if len(rows) > 1 and any("yoy_ratio" in row for row in rows):
            return "bar"
        if any(token in question for token in ["趋势", "变化", "走势", "可视化", "绘图", "图表", "画图"]):
            chart_type = select_chart_type(question, rows)
            return "无" if chart_type == "none" else chart_type
        return "无"

    def _chart_row_score(self, rows: list[dict[str, Any]]) -> tuple[int, int, int]:
        if not rows:
            return (0, 0, 0)
        has_priority_field = any(("stock_abbr" in row) or ("yoy_ratio" in row) for row in rows)
        return (1 if has_priority_field else 0, len(rows), 1)

    def _is_better_chart_result(self, candidate_rows: list[dict[str, Any]], current_rows: list[dict[str, Any]]) -> bool:
        if not candidate_rows:
            return False
        if not current_rows:
            return True
        return self._chart_row_score(candidate_rows) > self._chart_row_score(current_rows)

    def _is_superlative_question(self, question: str) -> bool:
        return any(token in question for token in ["最大", "最高", "最低", "最多", "最少", "最快", "最慢", "第一", "排名"])

    def _build_superlative_summary(self, question: str, row: dict[str, Any], intent: dict[str, Any], content: str) -> str:
        company = str(row.get("stock_abbr") or "该公司")
        if "yoy_ratio" in row and row.get("yoy_ratio") is not None:
            ratio = abs(float(row["yoy_ratio"])) * 100
            direction = "增长" if float(row["yoy_ratio"]) >= 0 else "下降"
            if "是" in question:
                prefix = question.split("是", 1)[0] + "是"
            else:
                prefix = "排名第一的是"
            return f"{prefix}{company}，同比{direction}{ratio:.2f}%。\n{content}"
        return f"排名第一的是{company}。\n{content}"


def format_research_answer_payload(answer: ResearchAnswer) -> str:
    """Build one turn's JSON per 附件7 表5 structure.

    Shape: {"Q": <question>, "A": {"content": <text>, "image": [], "references": [...]}}
    Image is populated later by the caller once a chart is rendered.
    """
    return json.dumps({
        "Q": answer.question,
        "A": {
            "content": answer.answer,
            "image": [],
            "references": [
                {"paper_path": ref.paper_path, "text": ref.text, "paper_image": ref.paper_image}
                for ref in answer.references
            ],
        },
    }, ensure_ascii=False)
