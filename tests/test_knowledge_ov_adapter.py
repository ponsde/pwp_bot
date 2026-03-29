from pathlib import Path

from src.knowledge.ov_adapter import search, store_resource


class FakeClient:
    def add_resource(self, path, wait=True, build_index=True):
        return {"uri": f"viking://{Path(path).name}"}

    def search(self, query, limit=10):
        return [{"text": f"match for {query}", "source": "paper.pdf", "score": 0.9}]


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
