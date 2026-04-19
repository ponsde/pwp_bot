"""Test OV concurrent add_resource — ingest 3 PDFs in parallel into a scratch OV dir.

Goal: confirm whether 2+ SyncOpenViking clients can share a data dir safely.
Run on the test server against 3 small research PDFs, writing to `.openviking_test/`.
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import shutil
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _worker(worker_id: int, data_path: str, pdf_path: str) -> dict:
    from src.knowledge.ov_adapter import init_client, store_resource

    t0 = time.time()
    try:
        client = init_client(data_path=data_path)
        uri = store_resource(client, pdf_path, wait=True)
        return {
            "worker_id": worker_id,
            "pdf": pdf_path,
            "status": "ok",
            "uri": uri,
            "elapsed": round(time.time() - t0, 2),
        }
    except Exception as exc:
        return {
            "worker_id": worker_id,
            "pdf": pdf_path,
            "status": "error",
            "error_type": type(exc).__name__,
            "error_msg": str(exc)[:500],
            "traceback": traceback.format_exc()[:2000],
            "elapsed": round(time.time() - t0, 2),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", default=".openviking_concurrent_test")
    parser.add_argument("--pdfs", nargs="+", required=True)
    parser.add_argument("--fresh", action="store_true", help="Wipe data path before starting")
    args = parser.parse_args()

    data_path = Path(args.data_path).resolve()
    if args.fresh and data_path.exists():
        print(f"[fresh] removing {data_path}")
        shutil.rmtree(data_path)
    data_path.mkdir(parents=True, exist_ok=True)

    pdfs = [str(Path(p).resolve()) for p in args.pdfs]
    print(f"[plan] scratch OV={data_path} | {len(pdfs)} PDFs in parallel")

    with mp.get_context("spawn").Pool(processes=len(pdfs)) as pool:
        results = pool.starmap(
            _worker,
            [(i, str(data_path), pdf) for i, pdf in enumerate(pdfs)],
        )

    import json
    print("=== RESULTS ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    ok = sum(1 for r in results if r["status"] == "ok")
    err = sum(1 for r in results if r["status"] == "error")
    print(f"\nSUMMARY: ok={ok} err={err} / {len(results)}")
    if err:
        print("VERDICT: OV does NOT support concurrent writes to same data-path.")
    else:
        print("VERDICT: OV appears to tolerate concurrent writes.")


if __name__ == "__main__":
    main()
