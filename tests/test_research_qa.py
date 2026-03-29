from src.knowledge.research_qa import ResearchQAEngine
from src.knowledge.retriever import RetrievalItem
from src.query.text2sql import QueryResult


class FakeRetriever:
    def search(self, query: str, top_k: int = 5):
        return [RetrievalItem(paper_path='./附件5：研报数据/个股研报/paper.pdf', text='国家医保目录新增了多个中药创新药。', score=0.9)]


class FakeSQL:
    def query(self, question, conversation=None):
        return QueryResult(sql='SELECT total_operating_revenue FROM income_sheet', rows=[{'total_operating_revenue': 100.0}], intent={})


class FakeEngine(ResearchQAEngine):
    def __init__(self):
        self.db_path = ':memory:'
        self.client = object()
        self.llm_client = None
        self.documents = []
        self.loaded_documents = []
        self.retriever = FakeRetriever()
        self.sql_engine = FakeSQL()


def test_classify_intent_routes_sql_rag_hybrid():
    engine = FakeEngine()
    assert engine.classify_intent('华润三九2025年主营业务收入是多少') == 'sql'
    assert engine.classify_intent('国家医保目录新增的中药产品有哪些') == 'rag'
    assert engine.classify_intent('主营业务收入上升的原因是什么') == 'hybrid'


def test_answer_rag_returns_references():
    engine = FakeEngine()
    answer = engine.answer_question('国家医保目录新增的中药产品有哪些')
    assert answer.route == 'rag'
    assert answer.references[0].paper_path == './附件5：研报数据/个股研报/paper.pdf'


def test_answer_hybrid_combines_sql_and_rag():
    engine = FakeEngine()
    answer = engine.answer_question('主营业务收入上升的原因是什么')
    assert answer.route == 'hybrid'
    assert '100.00万元' not in answer.answer
    assert answer.references
