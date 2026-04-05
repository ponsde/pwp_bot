from src.knowledge.research_qa import ResearchQAEngine
from src.knowledge.retriever import RetrievalItem
from src.query.constants import USER_VISIBLE_WARNING_WHITELIST
from src.query.conversation import ConversationManager
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


def test_answer_sql_forwards_company_context_between_sub_questions():
    class ForwardSQL:
        def __init__(self):
            self.calls = []

        def query(self, question, conversation=None):
            self.calls.append((question, list((conversation or ConversationManager()).slots.get('companies', []))))
            if 'top10' in question or 'top 10' in question or '最高' in question:
                return QueryResult(
                    sql='SELECT stock_abbr, net_profit FROM income_sheet ORDER BY net_profit DESC LIMIT 10',
                    rows=[{'stock_abbr': '华润三九', 'net_profit': 400000000}, {'stock_abbr': '同仁堂', 'net_profit': 500000000}],
                    intent={},
                )
            return QueryResult(
                sql='SELECT stock_abbr, yoy_ratio FROM income_sheet',
                rows=[{'stock_abbr': '华润三九', 'yoy_ratio': 0.1429}, {'stock_abbr': '同仁堂', 'yoy_ratio': 0.2500}],
                intent={'companies': []},
            )

    class ForwardEngine(FakeEngine):
        def __init__(self):
            super().__init__()
            self.sql_engine = ForwardSQL()

        def classify_intent(self, question: str) -> str:
            return 'sql'

        def split_multi_intent(self, question: str, conversation: ConversationManager | None = None) -> list[str]:
            return ['2024年净利润最高的top10企业是哪些？', '这些企业的净利润同比是多少？']

    engine = ForwardEngine()
    conv = ConversationManager()
    answer = engine.answer_question('2024年净利润最高的top10企业是哪些？这些企业的净利润同比是多少？', conv)
    assert answer.route == 'sql'
    assert engine.sql_engine.calls[0][1] == []
    assert engine.sql_engine.calls[1][1] == ['华润三九', '同仁堂']
    assert conv.slots['companies'] == ['华润三九', '同仁堂']


def test_select_chart_type_auto_triggers_for_top_n_and_yoy():
    engine = FakeEngine()
    assert engine._select_chart_type('2024年利润最高的top10企业是哪些', [{'stock_abbr': 'A', 'net_profit': 1}, {'stock_abbr': 'B', 'net_profit': 2}]) == 'bar'
    assert engine._select_chart_type('同比情况', [{'stock_abbr': 'A', 'yoy_ratio': 0.1}, {'stock_abbr': 'B', 'yoy_ratio': 0.2}]) == 'bar'
    assert engine._select_chart_type('华润三九2024年净利润是多少', [{'stock_abbr': '华润三九', 'net_profit': 1}]) == '无'


def test_superlative_subquestion_includes_company_and_metric_value():
    class SummarySQL:
        def query(self, question, conversation=None):
            return QueryResult(
                sql='SELECT stock_abbr, report_period, current_value, previous_value, yoy_ratio FROM income_sheet',
                rows=[{'stock_abbr': '金花股份', 'report_period': '2024FY', 'current_value': 3716.0, 'previous_value': 1000.0, 'yoy_ratio': 2.716}],
                intent={'fields': ['net_profit']},
            )

    class SummaryEngine(FakeEngine):
        def __init__(self):
            super().__init__()
            self.sql_engine = SummarySQL()

        def classify_intent(self, question: str) -> str:
            return 'sql'

        def split_multi_intent(self, question: str, conversation: ConversationManager | None = None) -> list[str]:
            return ['年同比上涨幅度最大的是哪家企业？']

    answer = SummaryEngine().answer_question('年同比上涨幅度最大的是哪家企业？')
    assert '金花股份' in answer.answer
    assert '271.60%' in answer.answer
    assert '同比增长' in answer.answer


def test_answer_sql_prefers_most_chartable_subquestion_result():
    class ChartSQL:
        def __init__(self):
            self.calls = 0

        def query(self, question, conversation=None):
            self.calls += 1
            if self.calls == 1:
                return QueryResult(
                    sql='SELECT report_period, total_profit FROM income_sheet',
                    rows=[{'report_period': '2024FY', 'total_profit': 10.0}],
                    intent={},
                )
            return QueryResult(
                sql='SELECT stock_abbr, yoy_ratio FROM income_sheet',
                rows=[
                    {'stock_abbr': 'A', 'yoy_ratio': 0.1},
                    {'stock_abbr': 'B', 'yoy_ratio': 0.2},
                    {'stock_abbr': 'C', 'yoy_ratio': 0.3},
                ],
                intent={'fields': ['net_profit']},
            )

    class ChartEngine(FakeEngine):
        def __init__(self):
            super().__init__()
            self.sql_engine = ChartSQL()

        def classify_intent(self, question: str) -> str:
            return 'sql'

        def split_multi_intent(self, question: str, conversation: ConversationManager | None = None) -> list[str]:
            return ['先问一个单行结果？', '再问同比排名结果？']

    answer = ChartEngine().answer_question('复合问题')
    assert answer.chart_rows == [
        {'stock_abbr': 'A', 'yoy_ratio': 0.1},
        {'stock_abbr': 'B', 'yoy_ratio': 0.2},
        {'stock_abbr': 'C', 'yoy_ratio': 0.3},
    ]
    assert answer.chart_type == 'bar'


def test_format_sql_result_does_not_append_warning_to_user_output():
    engine = FakeEngine()
    result = QueryResult(
        sql='SELECT net_profit FROM income_sheet',
        rows=[{'current_value': 10.0, 'previous_value': 0.0, 'yoy_ratio': None}],
        intent={'fields': ['net_profit']},
        warning=USER_VISIBLE_WARNING_WHITELIST[0],
    )

    content = engine._format_sql_result('华润三九2024年净利润同比', result)

    assert USER_VISIBLE_WARNING_WHITELIST[0] not in content
    assert '注：' not in content


def test_answer_sql_deduplicates_overlapping_lines_across_subquestions():
    class DedupSQL:
        def __init__(self):
            self.calls = 0

        def query(self, question, conversation=None):
            self.calls += 1
            if self.calls == 1:
                return QueryResult(
                    sql='SELECT stock_abbr, total_profit FROM income_sheet WHERE stock_abbr = "金花股份"',
                    rows=[{'stock_abbr': '金花股份', 'total_profit': 4203.93}],
                    intent={'fields': ['total_profit']},
                )
            return QueryResult(
                sql='SELECT stock_abbr, total_profit, yoy_ratio FROM income_sheet WHERE stock_abbr = "金花股份"',
                rows=[{'stock_abbr': '金花股份', 'total_profit': 4203.93}],
                intent={'fields': ['total_profit']},
            )

    class DedupEngine(FakeEngine):
        def __init__(self):
            super().__init__()
            self.sql_engine = DedupSQL()

        def classify_intent(self, question: str) -> str:
            return 'sql'

        def split_multi_intent(self, question: str, conversation: ConversationManager | None = None) -> list[str]:
            return ['先问利润总额？', '再问这些公司的利润总额？']

    answer = DedupEngine().answer_question('复合问题')

    assert answer.answer.count('金花股份：利润总额=4,203.93万元') == 1


def test_answer_sql_dedup_preserves_unique_lines_in_first_seen_order():
    engine = FakeEngine()
    text = '金花股份：利润总额=4,203.93万元\n华润三九：利润总额=1,000.00万元\n金花股份：利润总额=4,203.93万元\n同仁堂：利润总额=900.00万元'

    assert engine._deduplicate_answer_lines(text) == (
        '金花股份：利润总额=4,203.93万元\n'
        '华润三九：利润总额=1,000.00万元\n'
        '同仁堂：利润总额=900.00万元'
    )


def test_answer_sql_dedup_treats_whitespace_only_differences_as_duplicates():
    engine = FakeEngine()
    text = '金花股份：利润总额=4,203.93万元\n  金花股份：利润总额=4,203.93万元  \n同仁堂：利润总额=900.00万元'

    assert engine._deduplicate_answer_lines(text) == (
        '金花股份：利润总额=4,203.93万元\n'
        '同仁堂：利润总额=900.00万元'
    )
