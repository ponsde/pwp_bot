"""Persist a resource → category manifest so the backend can report the
research breakdown without needing the source 附件5 PDFs (which .gitignore
strips from the repo and Railway therefore never sees).

Output: .openviking/resources_manifest.json
Shape: {"stock": ["<sanitized_name>", ...], "industry": [...], "other": [...]}
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = ROOT / ".openviking" / "viking" / "default" / "resources"
RESEARCH_ROOT = ROOT / "data" / "sample" / "示例数据" / "附件5：研报数据"
MANIFEST = ROOT / ".openviking" / "resources_manifest.json"

_SAN = re.compile(r"[^\w\u4e00-\u9fff]")


def _sanitize(stem: str) -> str:
    return _SAN.sub("", stem)


def main() -> int:
    if not RESOURCES_DIR.exists():
        print(f"resources dir missing: {RESOURCES_DIR}", file=sys.stderr)
        return 1
    if not RESEARCH_ROOT.exists():
        print(f"research source missing: {RESEARCH_ROOT}", file=sys.stderr)
        return 1

    # Build sanitized_name → category from source PDFs
    cat_map: dict[str, str] = {}
    for sub_zh, label in (("个股研报", "stock"), ("行业研报", "industry")):
        for pdf in (RESEARCH_ROOT / sub_zh).glob("*.pdf"):
            cat_map[_sanitize(pdf.stem)] = label

    buckets: dict[str, list[str]] = {"stock": [], "industry": [], "other": []}
    for rsrc in sorted(RESOURCES_DIR.iterdir()):
        if not rsrc.is_dir():
            continue
        name = rsrc.name
        base = re.sub(r"_\d+$", "", name)
        cat = cat_map.get(base) or cat_map.get(name) or "other"
        buckets[cat].append(name)

    MANIFEST.write_text(
        json.dumps(buckets, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    totals = {k: len(v) for k, v in buckets.items()}
    print(f"wrote {MANIFEST}")
    print(f"  totals: {totals}  (sum={sum(totals.values())})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
