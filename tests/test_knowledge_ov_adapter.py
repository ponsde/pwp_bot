from pathlib import Path

from src.knowledge.ov_adapter import _extract_snippet, search, store_resource
from src.knowledge.research_loader import discover_research_documents
from src.knowledge.research_qa import ResearchQAEngine
from src.knowledge.retriever import RetrievalItem, ResearchRetriever
from src.query.text2sql import QueryResult


class FakeClient:
    def add_resource(self, path, wait=True, build_index=True):
        return {"uri": f"viking://{Path(path).name}"}

    def search(self, query, limit=10):
        return [{"text": f"match for {query}", "source": "paper.pdf", "score": 0.9}]


class FakeRetriever:
    def search(self, query: str, top_k: int = 5):
        return [RetrievalItem(paper_path='./附件5：研报数据/个股研报/paper.pdf', text='国家医保目录新增了多个中药创新药。', score=0.9)]


class FakeSQL:
    def __init__(self):
        self.calls = 0

    def query(self, question, conversation=None):
        self.calls += 1
        return QueryResult(
            sql='SELECT total_operating_revenue FROM income_sheet',
            rows=[{'report_period': '2025Q3', 'total_operating_revenue': 100.0}],
            intent={},
            warning='原始任务明确要求查询主营业务收入',
        )


class FakeEngine(ResearchQAEngine):
    def __init__(self):
        self.db_path = ':memory:'
        self.client = object()
        self.llm_client = None
        self.documents = []
        self.loaded_documents = []
        self.retriever = FakeRetriever()
        self.sql_engine = FakeSQL()


def test_store_resource_returns_uri(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    pdf.write_text("x", encoding="utf-8")
    uri = store_resource(FakeClient(), pdf)
    assert uri == "viking://sample.pdf"


def test_search_normalizes_results():
    results = search(FakeClient(), "华润三九", top_k=1)
    assert results[0]["text"] == "match for 华润三九"
    assert results[0]["source"] == "paper.pdf"
    assert results[0]["score"] == 0.9


def test_extract_snippet_prefers_short_context_window():
    text = '这是开头。' + '中药创新药纳入医保目录后放量明显，院内覆盖率持续提升。' * 20 + '这是结尾。'
    snippet = _extract_snippet(text, '医保目录 创新药')
    assert '医保目录' in snippet or '创新药' in snippet
    assert 50 < len(snippet) <= 500


def test_retriever_maps_viking_uri_to_relative_pdf_path():
    docs = discover_research_documents()
    target = next(doc for doc in docs if '内涵+外延双轮驱动' in doc.paper_path)

    class OVClient:
        def search(self, query, limit=10):
            return [{
                'text': '经营拐点已现，渠道调整完成后收入增速修复。',
                'source': 'viking://resources/2025年三季报点评：内涵+外延双轮驱动，经营拐点已现_2.md',
                'score': 0.95,
            }]

    item = ResearchRetriever(OVClient(), documents=docs).search('经营拐点', top_k=1)[0]
    assert item.paper_path == './附件5：研报数据/个股研报/' + Path(target.paper_path).name


def test_answer_hybrid_only_keeps_rag_analysis_and_sql_once():
    engine = FakeEngine()
    answer = engine.answer_question('主营业务收入上升的原因是什么')
    assert answer.route == 'hybrid'
    assert '100.00万元' not in answer.answer
    assert answer.sql == 'SELECT total_operating_revenue FROM income_sheet'
    assert answer.references


def test_format_sql_result_hides_warning_text():
    engine = FakeEngine()
    result = engine.sql_engine.query('test')
    formatted = engine._format_sql_result('test', result)
    assert 'warning' not in formatted.lower()
    assert '原始任务明确要求' not in formatted


def test_answer_sql_deduplicates_repeated_query_results():
    engine = FakeEngine()
    engine.split_multi_intent = lambda question, conversation=None: ['Q1', 'Q1']
    answer = engine.answer_question('华润三九近三年主营业务收入并可视化展示')
    assert answer.route == 'sql'
    assert answer.answer.count('100.00万元') == 1
    assert answer.chart_rows == [{'report_period': '2025Q3', 'total_operating_revenue': 100.0}]
