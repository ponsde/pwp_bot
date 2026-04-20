"""Parallel ETL runner — shards PDFs by stock code across workers, merges DBs at end."""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.etl.loader import ETLLoader
from src.etl.schema import load_company_mapping


SSE_FILE_RE = re.compile(r"^(\d{6})_\d{8}_[A-Z0-9]+\.pdf$")
SZSE_TITLE_RE = re.compile(r"^([^：:]+)[：:]20\d{2}年")


def _stock_code_from_filename(path: Path, abbr_to_code: dict[str, str]) -> str | None:
    name = path.name
    m = SSE_FILE_RE.match(name)
    if m:
        return m.group(1).zfill(6)
    m = SZSE_TITLE_RE.match(name)
    if m:
        abbr = m.group(1).strip()
        code = abbr_to_code.get(abbr)
        if code:
            return code.zfill(6)
    return None


def _shard_pdfs(input_dir: Path, num_shards: int) -> dict[int, list[Path]]:
    """Group PDFs by stock code, then assign groups to shards by best-fit to balance count.

    PDFs for the same company must land in the same shard so per-DB
    post-processing (growth-field YoY) has all periods available.
    """
    abbr_to_code = {entry["stock_abbr"]: entry["stock_code"] for entry in load_company_mapping().values()}
    groups: dict[str, list[Path]] = {}
    unknown_count = 0
    for pdf in sorted(input_dir.rglob("*.pdf")):
        code = _stock_code_from_filename(pdf, abbr_to_code)
        if code is None:
            unknown_count += 1
            key = f"__unknown_{unknown_count}"
        else:
            key = code
        groups.setdefault(key, []).append(pdf)
    shards: dict[int, list[Path]] = {i: [] for i in range(num_shards)}
    # Sort groups by descending size, greedy-assign to smallest current shard
    for key in sorted(groups, key=lambda k: -len(groups[k])):
        target = min(range(num_shards), key=lambda i: len(shards[i]))
        shards[target].extend(groups[key])
    if unknown_count:
        print(f"[shard] {unknown_count} PDFs with unknown stock code, each treated as its own group", flush=True)
    return shards


def _worker(worker_id: int, db_path: str, pdf_paths: list[str], log_path: str) -> dict:
    loader = ETLLoader(Path(db_path))
    stats = {"loaded": 0, "skipped": 0, "rejected": 0, "error": 0}
    with open(log_path, "w", encoding="utf-8") as logf:
        for i, pdf_str in enumerate(pdf_paths, 1):
            pdf = Path(pdf_str)
            try:
                result = loader.load_pdf(pdf)
                status = result["status"]
            except Exception as exc:
                status = "error"
                result = {"status": "error", "file": str(pdf), "error": str(exc), "reason": str(exc)}
            stats[status] = stats.get(status, 0) + 1
            warnings = result.get("warnings") or []
            reason = result.get("reason") or (warnings[0] if warnings else "")
            logf.write(f"{status}\t{pdf.name}\t{reason[:200]}\n")
            logf.flush()
    return {"worker_id": worker_id, "db_path": db_path, **stats}


def _merge_dbs(shard_dbs: list[Path], target_db: Path) -> None:
    """Merge shard DBs into target via ATTACH + INSERT OR REPLACE."""
    target_db.parent.mkdir(parents=True, exist_ok=True)
    if target_db.exists():
        target_db.unlink()
    # Initialize schema by running an ETLLoader on target (no PDFs processed)
    ETLLoader(target_db)
    tables = [
        "core_performance_indicators_sheet",
        "balance_sheet",
        "income_sheet",
        "cash_flow_sheet",
        "_share_capital_cache",
    ]
    with sqlite3.connect(target_db) as conn:
        for shard in shard_dbs:
            if not shard.exists():
                continue
            conn.execute(f"ATTACH DATABASE '{shard}' AS shard")
            try:
                for table in tables:
                    try:
                        conn.execute(f'INSERT OR REPLACE INTO "{table}" SELECT * FROM shard."{table}"')
                    except sqlite3.OperationalError as exc:
                        # table may not exist in shard if schema changed; skip safely
                        print(f"[merge] skip {shard.name}.{table}: {exc}", flush=True)
                conn.commit()
            finally:
                conn.execute("DETACH DATABASE shard")
        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--db-path", default="data/db/finance.db")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--shard-dir", default="data/db/shards")
    args = parser.parse_args()

    input_dir = Path(args.input).resolve()
    shard_dir = Path(args.shard_dir).resolve()
    shard_dir.mkdir(parents=True, exist_ok=True)
    log_dir = Path("logs").resolve()
    log_dir.mkdir(parents=True, exist_ok=True)

    shards = _shard_pdfs(input_dir, args.workers)
    total = sum(len(v) for v in shards.values())
    print(f"[shard] total PDFs: {total}, per-worker: {[len(v) for v in shards.values()]}", flush=True)

    shard_db_paths = [shard_dir / f"finance_shard_{i}.db" for i in range(args.workers)]
    for p in shard_db_paths:
        if p.exists():
            p.unlink()

    t0 = time.time()
    tasks = [
        (i, str(shard_db_paths[i]), [str(p) for p in shards[i]], str(log_dir / f"etl_shard_{i}.log"))
        for i in range(args.workers)
    ]
    with mp.get_context("spawn").Pool(processes=args.workers) as pool:
        results = pool.starmap(_worker, tasks)
    elapsed = time.time() - t0

    totals = {"loaded": 0, "skipped": 0, "rejected": 0, "error": 0}
    for r in results:
        for k in totals:
            totals[k] += r.get(k, 0)
    print(json.dumps({"workers": results, "totals": totals, "elapsed_sec": round(elapsed, 1)}, ensure_ascii=False, indent=2), flush=True)

    print(f"[merge] merging {len(shard_db_paths)} shard DBs into {args.db_path}", flush=True)
    _merge_dbs(shard_db_paths, Path(args.db_path))
    print(f"[done] total={total} loaded={totals['loaded']} skipped={totals['skipped']} rejected={totals['rejected']} error={totals['error']} elapsed={elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
