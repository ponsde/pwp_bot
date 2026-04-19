from src.knowledge.research_loader import discover_research_documents


def test_discover_research_documents_reads_sample_files():
    docs = discover_research_documents()
    # At least one stock + one industry report should be present. Exact count
    # depends on whether the demo sample or the full competition dataset is
    # mounted under data/sample/示例数据, so assert category coverage rather
    # than a fixed size.
    assert len(docs) >= 3
    assert any(doc.category == "stock" for doc in docs)
    assert any(doc.category == "industry" for doc in docs)
