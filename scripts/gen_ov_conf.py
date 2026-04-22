#!/usr/bin/env python3
"""Generate ov.conf from ov.conf.tmpl by substituting env vars from .env + process env.

Why this exists: vikingbot loads ov.conf as a static JSON and does not interpolate
${VAR} references. We want LLM_MODEL / LLM_API_KEY / LLM_API_BASE and a few other
values to come from .env (single source of truth) instead of being hardcoded.

Usage:
  python3 scripts/gen_ov_conf.py                  # writes ov.conf
  python3 scripts/gen_ov_conf.py --check          # verify ov.conf is up-to-date
  python3 scripts/gen_ov_conf.py -o /tmp/ov.conf  # custom output path

.env must be present at the repo root (same dir as ov.conf.tmpl).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from string import Template


REPO_ROOT = Path(__file__).resolve().parent.parent
TMPL_PATH = REPO_ROOT / "ov.conf.tmpl"
DEFAULT_OUTPUT = REPO_ROOT / "ov.conf"
ENV_FILE = REPO_ROOT / ".env"

DEFAULTS = {
    "OV_WORKSPACE": str(REPO_ROOT / ".openviking"),
    "REPO_ROOT": str(REPO_ROOT),
    "PYTHON_BIN": str(REPO_ROOT / ".venv" / "bin" / "python3"),
    "BOT_CHANNEL_API_KEY": "taidi-bot-key-2026",
}

REQUIRED_FROM_ENV = (
    "LLM_API_KEY",
    "LLM_API_BASE",
    "LLM_MODEL",
    "EMBEDDING_MODEL",
    "SQLITE_DB_PATH",
)


def load_dotenv(path: Path) -> dict:
    env = {}
    if not path.is_file():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def resolve(env_from_file: dict) -> dict:
    merged = dict(DEFAULTS)
    # .env values override defaults, real process env overrides .env
    for k, v in env_from_file.items():
        merged[k] = v
    for k in list(merged) + list(REQUIRED_FROM_ENV):
        if k in os.environ:
            merged[k] = os.environ[k]
    sqlite_raw = merged.get("SQLITE_DB_PATH", "data/db/finance.db")
    sqlite_abs = str((REPO_ROOT / sqlite_raw).resolve()) if not os.path.isabs(sqlite_raw) else sqlite_raw
    merged["SQLITE_DB_PATH_ABS"] = sqlite_abs
    return merged


def render(tmpl_text: str, values: dict) -> str:
    tmpl = Template(tmpl_text)
    missing = [name for _, name, _, _ in Template.pattern.findall(tmpl_text) if name and name not in values]
    # (Template.pattern groups are version-dependent; safe_substitute is lenient,
    # but here we want to fail fast on missing required keys.)
    missing_required = [k for k in REQUIRED_FROM_ENV if k not in values]
    if missing_required:
        raise SystemExit(f"ERROR: required env keys missing: {missing_required}. Check .env")
    return tmpl.substitute(values)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT))
    ap.add_argument("--check", action="store_true", help="exit 1 if output differs from freshly-rendered content")
    args = ap.parse_args()

    if not TMPL_PATH.is_file():
        raise SystemExit(f"ERROR: template missing: {TMPL_PATH}")

    values = resolve(load_dotenv(ENV_FILE))
    tmpl_text = TMPL_PATH.read_text(encoding="utf-8")
    rendered = render(tmpl_text, values)

    out_path = Path(args.output)
    if args.check:
        if not out_path.is_file():
            print(f"CHECK FAIL: {out_path} does not exist")
            return 1
        existing = out_path.read_text(encoding="utf-8")
        if existing != rendered:
            print(f"CHECK FAIL: {out_path} is stale — rerun scripts/gen_ov_conf.py to regenerate")
            return 1
        print(f"OK: {out_path} matches template + env")
        return 0

    out_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"  LLM_MODEL     = {values['LLM_MODEL']}")
    print(f"  LLM_API_BASE  = {values['LLM_API_BASE']}")
    print(f"  EMBEDDING_MODEL = {values['EMBEDDING_MODEL']}")
    print(f"  SQLITE_DB_PATH = {values['SQLITE_DB_PATH_ABS']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
