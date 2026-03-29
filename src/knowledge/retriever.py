"""Research retrieval helpers with source formatting."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.knowledge.ov_adapter import search as ov_search
from src.knowledge.research_loader import discover_research_documents


@dataclass(frozen=True)
class RetrievalItem:
    paper_path: str
    text: str
    score: float
    paper_image: str = ""


class ResearchRetriever:
    def __init__(self, client: Any, documents: list[Any] | None = None):
        self.client = client
        self.documents = documents or discover_research_documents()
        self.known_papers = [doc.paper_path for doc in self.documents]

    def search(self, query: str, top_k: int = 5) -> list[RetrievalItem]:
        results = ov_search(self.client, query, top_k=top_k)
        items: list[RetrievalItem] = []
        for result in results:
            source = str(result.get("source", ""))
            paper_path = source
            for known in self.known_papers:
                normalized = known.replace('\\', '/')
                if normalized in source.replace('\\', '/') or Path(normalized).stem in source:
                    paper_path = known
                    break
            items.append(RetrievalItem(paper_path=paper_path, text=str(result.get("text", "")).strip(), score=float(result.get("score", 0.0))))
        return items
