"""Bulk-ingest research PDFs into OpenViking.

Loops over 附件5 PDFs (个股 + 行业) and calls store_resource.
Prints one status line per PDF so a Monitor filter can stream progress.
Resumes gracefully — skips resources already present in OV's viking/default/resources.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.knowledge.ov_adapter import init_client, store_resource


_SANITIZE_RE = re.compile(r"[^\w\u4e00-\u9fff]")


def _sanitize_name(title: str) -> str:
    return _SANITIZE_RE.sub("", title)


def _existing_resource_names(ov_root: Path) -> set[str]:
    resources_dir = ov_root / "viking" / "default" / "resources"
    if not resources_dir.exists():
        return set()
    return {p.name for p in resources_dir.iterdir() if p.is_dir()}


def _pdf_iter(research_root: Path):
    for sub in ("个股研报", "行业研报"):
        for pdf in sorted((research_root / sub).glob("*.pdf")):
            yield pdf, sub


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/sample/示例数据/附件5：研报数据")
    parser.add_argument("--ov-data", default=".openviking")
    parser.add_argument("--limit", type=int, default=0, help="Max PDFs to process (0=all)")
    args = parser.parse_args()

    research_root = Path(args.root).resolve()
    ov_root = Path(args.ov_data).resolve()
    existing = _existing_resource_names(ov_root)
    print(f"[init] existing OV resources: {len(existing)}", flush=True)

    client = init_client()
    print("[init] OV client ready", flush=True)

    pdfs = list(_pdf_iter(research_root))
    if args.limit > 0:
        pdfs = pdfs[: args.limit]
    total = len(pdfs)
    print(f"[plan] total PDFs to process: {total}", flush=True)

    stats = {"ok": 0, "skipped": 0, "error": 0}
    t_start = time.time()
    for idx, (pdf, sub) in enumerate(pdfs, 1):
        stem = pdf.stem
        sanitized = _sanitize_name(stem)
        if sanitized in existing:
            stats["skipped"] += 1
            print(f"[{idx}/{total}] SKIP {sub}/{pdf.name}", flush=True)
            continue
        t0 = time.time()
        try:
            uri = store_resource(client, pdf, wait=True)
            elapsed = time.time() - t0
            stats["ok"] += 1
            print(f"[{idx}/{total}] OK {sub}/{pdf.name} elapsed={elapsed:.1f}s uri={uri}", flush=True)
        except Exception as exc:
            elapsed = time.time() - t0
            stats["error"] += 1
            print(f"[{idx}/{total}] ERR {sub}/{pdf.name} elapsed={elapsed:.1f}s err={type(exc).__name__}: {str(exc)[:200]}", flush=True)

    total_elapsed = time.time() - t_start
    print(f"[done] {json.dumps(stats)} total_elapsed={total_elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
