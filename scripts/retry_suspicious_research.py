"""Re-index 'suspicious' research PDFs (audit says log=OK but no confirmed OV dir).

Idempotent: if an OV resource still exists for the sanitized title, we delete
the directory first so add_resource creates a fresh one. Safe to run multiple
times.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.knowledge.ov_adapter import init_client, store_resource


_SANITIZE_RE = re.compile(r"[^\w\u4e00-\u9fff]")


def _sanitize_name(title: str) -> str:
    return _SANITIZE_RE.sub("", title)


def _find_matching_dirs(resources_dir: Path, sanitized: str) -> list[Path]:
    """Return directories matching the sanitized name, including `_1 _2` suffixes."""
    if not resources_dir.exists():
        return []
    pattern = re.compile(rf"^{re.escape(sanitized)}(_\d+)?$")
    return [p for p in resources_dir.iterdir() if p.is_dir() and pattern.match(p.name)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", default="logs/research_audit.json")
    parser.add_argument("--root", default="data/sample/示例数据/附件5：研报数据")
    parser.add_argument("--ov-data", default=".openviking")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delete-existing", action="store_true",
                        help="Delete matching OV dirs before re-ingesting")
    args = parser.parse_args()

    audit_path = Path(args.audit)
    root = Path(args.root).resolve()
    ov_root = Path(args.ov_data).resolve()
    resources_dir = ov_root / "viking" / "default" / "resources"

    if not audit_path.exists():
        print(f"[fatal] audit file not found: {audit_path}")
        sys.exit(1)
    report = json.loads(audit_path.read_text(encoding="utf-8"))
    suspicious_entries = report.get("suspicious_entries", [])
    if not suspicious_entries:
        print("[ok] no suspicious entries to retry")
        return
    print(f"[plan] {len(suspicious_entries)} suspicious PDFs to retry")

    if args.dry_run:
        for e in suspicious_entries:
            matches = _find_matching_dirs(resources_dir, e["sanitized_name"])
            print(f"  [dry] {e['sub']}/{e['pdf']} | matching dirs: {[m.name for m in matches]}")
        return

    client = init_client()

    stats = {"ok": 0, "error": 0, "verified_existing": 0}
    for idx, entry in enumerate(suspicious_entries, 1):
        sub, pdf_name = entry["sub"], entry["pdf"]
        sanitized = entry["sanitized_name"]
        pdf_path = root / sub / pdf_name
        if not pdf_path.exists():
            print(f"[{idx}/{len(suspicious_entries)}] SKIP {pdf_name}: source PDF missing")
            continue

        matches = _find_matching_dirs(resources_dir, sanitized)
        if matches and not args.delete_existing:
            # OV did index it, just with a suffix (_1) — audit was a false
            # positive. Accept existing state.
            stats["verified_existing"] += 1
            print(f"[{idx}/{len(suspicious_entries)}] VERIFIED {pdf_name} "
                  f"(existing dirs: {[m.name for m in matches]})")
            continue
        if matches and args.delete_existing:
            for m in matches:
                print(f"  [delete] {m}")
                shutil.rmtree(m)

        t0 = time.time()
        try:
            uri = store_resource(client, pdf_path, wait=True)
            stats["ok"] += 1
            print(f"[{idx}/{len(suspicious_entries)}] OK {pdf_name} "
                  f"elapsed={time.time() - t0:.1f}s uri={uri}")
        except Exception as exc:
            stats["error"] += 1
            print(f"[{idx}/{len(suspicious_entries)}] ERR {pdf_name} "
                  f"err={type(exc).__name__}: {str(exc)[:200]}")

    print(f"[done] {json.dumps(stats)}")


if __name__ == "__main__":
    main()
