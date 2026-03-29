from src.knowledge.research_loader import discover_research_documents


def test_discover_research_documents_reads_sample_files():
    docs = discover_research_documents()
    assert len(docs) == 3
    assert any("华润三九" in str(doc.metadata.get("stockName", "")) for doc in docs if doc.category == "stock")
    assert any(doc.category == "industry" for doc in docs)
