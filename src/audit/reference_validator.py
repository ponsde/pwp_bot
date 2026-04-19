"""Validate a single reference dict extracted from result_3.xlsx 回答 JSON.

A reference is considered valid iff:
  1. paper_path points to a real file on disk (relative to repo_root).
  2. text is either empty OR has a >=5-consecutive-char match inside any
     .md chunk of the matching OV resource.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_SAN = re.compile(r"[^\w\u4e00-\u9fff]")
_MIN_MATCH_CHARS = 5


@dataclass(frozen=True)
class RefResult:
    path_ok: bool
    text_ok: bool


def _sanitize(stem: str) -> str:
    return _SAN.sub("", stem)


def validate_reference(
    *, ref: dict, repo_root: Path, ov_root: Path
) -> RefResult:
    paper_path = (ref.get("paper_path") or "").strip()
    text = (ref.get("text") or "").strip()

    path_ok = False
    if paper_path and not paper_path.startswith("viking://"):
        # The submission spec wants paths relative to the evaluator's working
        # directory, i.e. "./附件5：研报数据/...". Locally the PDFs actually
        # live under "./data/sample/示例数据/附件5：研报数据/..." because of
        # how the repo stashes dev data. Try both.
        p = Path(paper_path)
        if p.is_absolute():
            path_ok = p.is_file()
        else:
            rel = paper_path.lstrip("./")
            for base in (repo_root, repo_root / "data" / "sample" / "示例数据"):
                if (base / rel).is_file():
                    path_ok = True
                    break

    if not text:
        return RefResult(path_ok=path_ok, text_ok=True)

    resources_root = ov_root / "viking" / "default" / "resources"
    if not resources_root.is_dir():
        return RefResult(path_ok=path_ok, text_ok=False)

    stem = Path(paper_path).stem
    key = _sanitize(stem)
    candidate_dirs = [
        d for d in resources_root.iterdir()
        if d.is_dir() and (_sanitize(d.name) == key or d.name == stem)
    ]
    if not candidate_dirs:
        candidate_dirs = [d for d in resources_root.iterdir() if d.is_dir()]

    slice_probe = re.sub(r"\s+", "", text)
    if len(slice_probe) < _MIN_MATCH_CHARS:
        return RefResult(path_ok=path_ok, text_ok=True)
    probe = slice_probe[:_MIN_MATCH_CHARS]

    for d in candidate_dirs:
        for md in d.glob("*.md"):
            try:
                body = md.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if probe in re.sub(r"\s+", "", body):
                return RefResult(path_ok=path_ok, text_ok=True)
    return RefResult(path_ok=path_ok, text_ok=False)
