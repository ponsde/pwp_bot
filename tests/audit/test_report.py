from src.audit.checks import Finding
from src.audit.report import render_report


def test_render_report_groups_by_severity():
    findings = [
        Finding("B1001", "blocking", "num_mismatch", "1 元 vs 100 元"),
        Finding("B2003", "suspect", "ref_text_miss", "text not in md"),
        Finding("B1002", "hint", "short_content", "len<30"),
    ]
    md = render_report(findings, totals={"blocking": 1, "suspect": 1, "hint": 1})
    assert "## 阻塞" in md and "B1001" in md
    assert "## 可疑" in md and "B2003" in md
    assert "## 提示" in md and "B1002" in md


def test_render_report_empty_totals_message():
    md = render_report([], totals={"blocking": 0, "suspect": 0, "hint": 0})
    assert "全部通过" in md
