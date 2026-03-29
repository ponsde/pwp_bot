"""Research retrieval helpers with source formatting."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from src.knowledge.ov_adapter import search as ov_search
from src.knowledge.research_loader import RESEARCH_ROOT, discover_research_documents

_PUNCT_RE = re.compile(r"[：:，,。.；;、+\-—\s（）()【】\[\]《》]")


def _strip_punct(text: str) -> str:
    """Strip punctuation/whitespace for fuzzy matching between OV names and PDF stems."""
    return _PUNCT_RE.sub("", text)


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
        self._paper_lookup: dict[str, list[str]] = defaultdict(list)
        for path in self.known_papers:
            self._paper_lookup[Path(path).stem].append(path)
        # Pre-compute punctuation-stripped stems for fuzzy matching
        self._stripped_stems: dict[str, str] = {
            _strip_punct(Path(p).stem): p for p in self.known_papers
        }

    def _normalize_relative_paper_path(self, source: str) -> str:
        normalized_source = str(source or "").replace('\\', '/')
        source_name = PurePosixPath(normalized_source).name
        stem_candidates = [Path(source_name).stem, source_name]
        if source_name.endswith('.overview.md'):
            stem_candidates.append(source_name[:-len('.overview.md')])
        if source_name.endswith('.md'):
            stem_candidates.append(source_name[:-3])

        # Layer 1: exact path/stem substring match
        for known in self.known_papers:
            normalized_known = known.replace('\\', '/')
            if normalized_known in normalized_source or Path(normalized_known).stem in normalized_source:
                return self._to_relative_path(known)

        # Layer 2: exact stem lookup
        for stem in stem_candidates:
            matches = self._paper_lookup.get(stem, [])
            if len(matches) == 1:
                return self._to_relative_path(matches[0])
            if len(matches) > 1:
                source_parts = set(PurePosixPath(normalized_source).parts)
                for match in matches:
                    match_parts = set(PurePosixPath(match.replace('\\', '/')).parts)
                    if source_parts & match_parts:
                        return self._to_relative_path(match)
                return self._to_relative_path(matches[0])

        # Layer 3: fuzzy match — strip punctuation from OV URI and known stems
        # OV URIs like viking://resources/TITLE_STRIPPED/section/chunk.md
        # contain the PDF title (punct-stripped) as the first path segment
        stripped_source = _strip_punct(normalized_source)
        for stripped_stem, paper_path in self._stripped_stems.items():
            if stripped_stem in stripped_source or stripped_source and stripped_source in stripped_stem:
                return self._to_relative_path(paper_path)

        # Layer 4: try matching OV URI first segment against known stems
        uri_parts = [p for p in normalized_source.replace("viking://resources/", "").split("/") if p]
        if uri_parts:
            first_segment = _strip_punct(uri_parts[0])
            for stripped_stem, paper_path in self._stripped_stems.items():
                if first_segment and (first_segment == stripped_stem or first_segment in stripped_stem or stripped_stem in first_segment):
                    return self._to_relative_path(paper_path)

        return self._to_relative_path(source_name or normalized_source)

    def _to_relative_path(self, path: str) -> str:
        raw = str(path).replace('\\', '/')
        try:
            relative = Path(raw).resolve().relative_to(RESEARCH_ROOT.parent.resolve())
            return './' + relative.as_posix()
        except Exception:
            marker = '附件5：研报数据/'
            if marker in raw:
                return './' + marker + raw.split(marker, 1)[1]
            return raw

    def search(self, query: str, top_k: int = 5) -> list[RetrievalItem]:
        results = ov_search(self.client, query, top_k=top_k)
        items: list[RetrievalItem] = []
        for result in results:
            paper_path = self._normalize_relative_paper_path(str(result.get("source", "")))
            items.append(RetrievalItem(paper_path=paper_path, text=str(result.get("text", "")).strip(), score=float(result.get("score", 0.0))))
        return items
