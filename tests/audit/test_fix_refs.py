import json
from pathlib import Path

from scripts.fix_audit_findings import clean_broken_refs_in_cell


def test_clean_refs_drops_bad_paper_path(tmp_path: Path):
    (tmp_path / "ok.pdf").write_bytes(b"x")
    cell = json.dumps(
        [{"Q": "x", "A": {"content": "y", "references": [
            {"paper_path": str(tmp_path / "ok.pdf"), "text": "", "paper_image": ""},
            {"paper_path": str(tmp_path / "missing.pdf"), "text": "", "paper_image": ""},
        ]}}],
        ensure_ascii=False,
    )
    cleaned = clean_broken_refs_in_cell(cell, repo_root=tmp_path, ov_root=tmp_path)
    data = json.loads(cleaned)
    refs = data[0]["A"]["references"]
    assert len(refs) == 1 and refs[0]["paper_path"].endswith("ok.pdf")


def test_clean_refs_drops_empty_paper_path(tmp_path: Path):
    cell = json.dumps(
        [{"Q": "x", "A": {"content": "y", "references": [
            {"paper_path": "", "text": "", "paper_image": ""},
        ]}}],
        ensure_ascii=False,
    )
    cleaned = clean_broken_refs_in_cell(cell, repo_root=tmp_path, ov_root=tmp_path)
    assert json.loads(cleaned)[0]["A"]["references"] == []


def test_clean_refs_noop_on_malformed_cell(tmp_path: Path):
    assert clean_broken_refs_in_cell("not json", repo_root=tmp_path, ov_root=tmp_path) == "not json"
