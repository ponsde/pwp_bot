#!/bin/bash
# Waits for RAG index to finish → retries suspicious → generates result_3.
set -e
cd ~/taidi_bei

echo "[auto_result3] $(date) waiting for RAG indexer to exit..."
while pgrep -f 'python.*index_research.py' > /dev/null 2>&1; do sleep 60; done
echo "[auto_result3] $(date) RAG indexer exited"

echo "[auto_result3] $(date) running audit..."
.venv/bin/python scripts/audit_research_index.py 2>&1 | tail -15

echo "[auto_result3] $(date) retrying suspicious PDFs (delete + re-ingest)..."
.venv/bin/python scripts/retry_suspicious_research.py --delete-existing 2>&1 | tail -50

echo "[auto_result3] $(date) re-running audit after retry..."
.venv/bin/python scripts/audit_research_index.py 2>&1 | tail -15

# Wait for ETL + result_2 to be done (defensive — result_2 should already be there)
while [ ! -f data/db/finance.db ] || pgrep -f 'pipeline.py --task answer' > /dev/null 2>&1; do
  echo "[auto_result3] $(date) waiting for finance.db / answer pipeline..."
  sleep 60
done

echo "[auto_result3] $(date) kicking off run_research..."
mkdir -p result
.venv/bin/python -u pipeline.py --task research \
  --db-path data/db/finance.db \
  --questions 'data/sample/示例数据/附件6：问题汇总.xlsx' \
  --output result_3.xlsx 2>&1 | tee logs/run_research.log
echo "[auto_result3] $(date) DONE. result_3.xlsx written."
