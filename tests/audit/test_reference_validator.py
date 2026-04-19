from pathlib import Path

from src.audit.reference_validator import validate_reference, RefResult


def test_validate_reference_path_missing(tmp_path: Path):
    r = validate_reference(
        ref={"paper_path": str(tmp_path / "nope.pdf"), "text": "x"},
        repo_root=tmp_path,
        ov_root=tmp_path,
    )
    assert r.path_ok is False


def test_validate_reference_path_ok(tmp_path: Path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"fake")
    r = validate_reference(
        ref={"paper_path": str(p), "text": ""},
        repo_root=tmp_path,
        ov_root=tmp_path,
    )
    assert r.path_ok is True


def test_validate_reference_text_matches_resource_chunk(tmp_path: Path):
    ov_root = tmp_path / "ov"
    res = ov_root / "viking" / "default" / "resources" / "myreport"
    res.mkdir(parents=True)
    (res / "myreport_1.md").write_text(
        "国家医保局 25 年 8 月公告初步审评的中成药共 23 种。", encoding="utf-8"
    )
    ref = {
        "paper_path": "./附件5：研报数据/行业研报/myreport.pdf",
        "text": "国家医保局 25 年 8 月公告初步审评",
    }
    r = validate_reference(
        ref=ref,
        repo_root=tmp_path,
        ov_root=ov_root,
    )
    assert r.text_ok is True


def test_validate_reference_text_no_match(tmp_path: Path):
    ov_root = tmp_path / "ov"
    res = ov_root / "viking" / "default" / "resources" / "myreport"
    res.mkdir(parents=True)
    (res / "myreport_1.md").write_text("完全不相关的内容", encoding="utf-8")
    ref = {
        "paper_path": "./附件5：研报数据/行业研报/myreport.pdf",
        "text": "国家医保局 25 年 8 月",
    }
    r = validate_reference(
        ref=ref,
        repo_root=tmp_path,
        ov_root=ov_root,
    )
    assert r.text_ok is False


def test_validate_reference_ignores_viking_user_uri(tmp_path: Path):
    r = validate_reference(
        ref={"paper_path": "viking://user/foo", "text": ""},
        repo_root=tmp_path,
        ov_root=tmp_path,
    )
    assert r.path_ok is False
