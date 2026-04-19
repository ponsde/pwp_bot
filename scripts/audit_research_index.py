"""Audit OV research-index progress. Writes a JSON roster of success / error / pending.

Does NOT retry or re-index — purely a read-only report so we can decide later
when the upstream is stable. Safe to run while the main indexer is still working.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_SANITIZE_RE = re.compile(r"[^\w\u4e00-\u9fff]")
LOG_OK_RE = re.compile(r"^\[(\d+)/\d+\] OK (\S+?)/(.+?\.pdf) elapsed=([\d.]+)s uri=(.+)$")
LOG_ERR_RE = re.compile(r"^\[(\d+)/\d+\] ERR (\S+?)/(.+?\.pdf) elapsed=([\d.]+)s err=(.+)$")
LOG_SKIP_RE = re.compile(r"^\[(\d+)/\d+\] SKIP (\S+?)/(.+?\.pdf)$")


def _sanitize_name(title: str) -> str:
    return _SANITIZE_RE.sub("", title)


def _parse_log(log_path: Path) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    """Return (ok, err, skip) maps keyed by pdf basename."""
    ok, err, skip = {}, {}, {}
    if not log_path.exists():
        return ok, err, skip
    for line in log_path.read_text(encoding="utf-8").splitlines():
        m = LOG_OK_RE.match(line)
        if m:
            idx, sub, name, elapsed, uri = m.groups()
            ok[name] = {"index": int(idx), "sub": sub, "elapsed": float(elapsed), "uri": uri}
            continue
        m = LOG_ERR_RE.match(line)
        if m:
            idx, sub, name, elapsed, err_msg = m.groups()
            err[name] = {"index": int(idx), "sub": sub, "elapsed": float(elapsed), "error": err_msg[:500]}
            continue
        m = LOG_SKIP_RE.match(line)
        if m:
            idx, sub, name = m.groups()
            skip[name] = {"index": int(idx), "sub": sub}
    return ok, err, skip


def _discovered_resource_names(ov_root: Path) -> set[str]:
    resources_dir = ov_root / "viking" / "default" / "resources"
    if not resources_dir.exists():
        return set()
    return {p.name for p in resources_dir.iterdir() if p.is_dir()}


def _all_source_pdfs(research_root: Path) -> list[tuple[str, Path]]:
    out = []
    for sub in ("个股研报", "行业研报"):
        for pdf in sorted((research_root / sub).glob("*.pdf")):
            out.append((sub, pdf))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="logs/index_research.log")
    parser.add_argument("--ov-data", default=".openviking")
    parser.add_argument("--root", default="data/sample/示例数据/附件5：研报数据")
    parser.add_argument("--out", default="logs/research_audit.json")
    args = parser.parse_args()

    log_path = Path(args.log)
    ov_root = Path(args.ov_data)
    research_root = Path(args.root)
    out_path = Path(args.out)

    ok, err, skip = _parse_log(log_path)
    existing_dirs = _discovered_resource_names(ov_root)
    all_pdfs = _all_source_pdfs(research_root)

    missing = []      # PDFs never logged as OK/ERR/SKIP — e.g. indexer didn't get there yet
    suspicious = []   # PDFs logged ERR or where log said OK but no OV dir
    confirmed_ok = [] # PDFs logged OK and OV dir present

    for sub, pdf in all_pdfs:
        name = pdf.name
        sanitized = _sanitize_name(pdf.stem)
        log_ok = name in ok
        log_err = name in err
        log_skip = name in skip
        has_dir = sanitized in existing_dirs
        entry = {
            "sub": sub,
            "pdf": name,
            "sanitized_name": sanitized,
            "has_ov_dir": has_dir,
            "log_status": ("ok" if log_ok else "err" if log_err else "skip" if log_skip else "pending"),
        }
        if log_err:
            entry["error"] = err[name]["error"]
            suspicious.append(entry)
        elif log_ok and not has_dir:
            entry["warn"] = "log=OK but OV dir missing — possibly cleaned up or path mismatch"
            suspicious.append(entry)
        elif log_ok and has_dir:
            confirmed_ok.append(entry)
        elif log_skip and has_dir:
            confirmed_ok.append(entry)
        else:
            missing.append(entry)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "log_file": str(log_path),
        "total_source_pdfs": len(all_pdfs),
        "log_ok_count": len(ok),
        "log_err_count": len(err),
        "log_skip_count": len(skip),
        "ov_dir_count": len(existing_dirs),
        "confirmed_ok": len(confirmed_ok),
        "suspicious": len(suspicious),
        "missing": len(missing),
        "suspicious_entries": suspicious,
        "missing_entries": missing,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== Research RAG audit ===")
    print(f"total pdfs          : {report['total_source_pdfs']}")
    print(f"log OK              : {report['log_ok_count']}")
    print(f"log ERR             : {report['log_err_count']}")
    print(f"log SKIP            : {report['log_skip_count']}")
    print(f"OV dirs             : {report['ov_dir_count']}")
    print(f"CONFIRMED OK        : {report['confirmed_ok']}")
    print(f"SUSPICIOUS (need re-run): {report['suspicious']}")
    print(f"MISSING (not reached)   : {report['missing']}")
    print(f"Report written to: {out_path}")


if __name__ == "__main__":
    main()
