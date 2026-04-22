"""Batch-evaluate 附件4 / 附件6 through the local vikingbot gateway.

For each question:
- Create a new session
- Send each turn's Q as a separate POST /bot/v1/chat
- Parse events for SQL (mcp_fin_sql, mcp_fin_query), references
  (openviking_search), and image URLs (mcp_fin_query.chart_url)
- Format output per 附件7 表3 (answer) / 表6 (research)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_GATEWAY = "http://localhost:18790"
DEFAULT_API_KEY = "taidi-bot-key-2026"


def _load_questions_xlsx(path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()
    out = []
    for row in rows:
        if not row or not row[0]:
            continue
        qid = str(row[0]).strip()
        turns = json.loads(str(row[2])) if row[2] else []
        out.append({"id": qid, "turns": turns})
    return out


def _chat(gateway: str, api_key: str, session_id: str, message: str, timeout: int = 900) -> dict:
    resp = requests.post(
        f"{gateway}/bot/v1/chat",
        json={"message": message, "session_id": session_id},
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_tool_call(event: dict) -> tuple[str, dict]:
    """Return (tool_name, args_dict) from a tool_call event string like
    `mcp_fin_sql({"sql": "..."})`."""
    raw = str(event.get("data") or "")
    m = re.match(r"^([\w:]+)\((.*)\)$", raw, re.DOTALL)
    if not m:
        return "", {}
    tool, args_raw = m.group(1), m.group(2)
    try:
        args = json.loads(args_raw) if args_raw.strip() else {}
    except json.JSONDecodeError:
        args = {"_raw": args_raw}
    return tool, args


def _parse_tool_result(event: dict) -> Any:
    raw = str(event.get("data") or "")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # vikingbot serializes some tool results as a str(dict) with single quotes
    # and Enum reprs (e.g. `ContextType.MEMORY`). Sometimes the Enum is bare
    # (`'context_type': ContextType.MEMORY,`), sometimes already quoted as
    # str(enum) (`'ContextType.MEMORY'`). Strip the `ContextType.` prefix in
    # both cases; leave the rest intact for ast.literal_eval.
    cleaned = re.sub(r"'ContextType\.(\w+)'", r"'\1'", raw)
    cleaned = re.sub(r"(?<!')ContextType\.(\w+)", r"'\1'", cleaned)
    try:
        import ast
        return ast.literal_eval(cleaned)
    except (SyntaxError, ValueError):
        return raw


def _extract_sql(events: list[dict]) -> list[str]:
    sqls: list[str] = []
    for i, ev in enumerate(events):
        if ev.get("type") != "tool_call":
            continue
        tool, args = _parse_tool_call(ev)
        if tool == "MCP_fin_sql":
            sql = args.get("sql", "").strip()
            if sql:
                sqls.append(sql)
        elif tool == "MCP_fin_query":
            # Follow-up tool_result may contain a generated SQL.
            if i + 1 < len(events) and events[i + 1].get("type") == "tool_result":
                parsed = _parse_tool_result(events[i + 1])
                if isinstance(parsed, dict) and parsed.get("sql"):
                    sqls.append(str(parsed["sql"]).strip())
    return sqls


def _extract_references(events: list[dict]) -> list[dict]:
    refs: list[dict] = []
    for i, ev in enumerate(events):
        if ev.get("type") != "tool_call":
            continue
        tool, args = _parse_tool_call(ev)
        if tool not in {"openviking_search", "MCP_fin_query"}:
            continue
        if i + 1 >= len(events) or events[i + 1].get("type") != "tool_result":
            continue
        parsed = _parse_tool_result(events[i + 1])
        if not isinstance(parsed, dict):
            continue
        # OV /api/v1/search/find returns a dict like
        #   {"status":"ok","result":{"resources":[...],"memories":[...]}}
        # but by the time it reaches the bot-event stream, the outer wrapper
        # is already unwrapped — parsed is `{"resources":[...], ...}`.
        # mcp_fin_query uses a `sources` list of strings.
        items = []
        for key in ("resources", "memories", "sources", "matches", "results"):
            val = parsed.get(key)
            if isinstance(val, list):
                items.extend(val)
        for item in items:
            if isinstance(item, str):
                # mcp_fin_query's "sources" is plain strings like "SQL查询: ..." / "来源文档: viking://xxx — 摘要..."
                path = ""
                text = item
                if item.startswith("来源文档:"):
                    segments = item[len("来源文档:"):].strip()
                    if " — " in segments:
                        path, text = segments.split(" — ", 1)
                    else:
                        path, text = segments, ""
                refs.append({"paper_path": path.strip(), "text": text.strip()[:500], "paper_image": ""})
                continue
            if not isinstance(item, dict):
                continue
            path = str(item.get("paper_path") or item.get("path") or item.get("uri") or "").strip()
            text = str(
                item.get("text") or item.get("abstract") or item.get("overview")
                or item.get("context") or ""
            ).strip()
            image = str(item.get("paper_image") or item.get("image") or "").strip()
            if path or text:
                # Turn viking:// uri into a readable path for 附件7 reference format
                if path.startswith("viking://resources/"):
                    path = "./" + path[len("viking://"):]
                refs.append({"paper_path": path, "text": text[:500], "paper_image": image})
    # Dedup by (path, text)
    seen = set()
    out = []
    for r in refs:
        key = (r["paper_path"], r["text"][:100])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _extract_chart_info(events: list[dict]) -> tuple[str, list[str]]:
    chart_type = "无"
    images: list[str] = []
    for i, ev in enumerate(events):
        if ev.get("type") != "tool_call":
            continue
        tool, _args = _parse_tool_call(ev)
        if tool != "MCP_fin_query":
            continue
        if i + 1 >= len(events) or events[i + 1].get("type") != "tool_result":
            continue
        parsed = _parse_tool_result(events[i + 1])
        if not isinstance(parsed, dict):
            continue
        ct = parsed.get("chart_type")
        cu = parsed.get("chart_url")
        if ct and ct != "无":
            chart_type = ct
        if cu:
            images.append(str(cu))
    return chart_type, images


def _bot_run_question(gateway: str, api_key: str, item: dict, out_result_dir: Path, mode: str) -> dict:
    qid = item["id"]
    turns = item["turns"]
    session_id = f"{qid}-{uuid.uuid4().hex[:6]}"
    per_turn_payloads: list[dict] = []
    all_sql: list[str] = []
    all_refs: list[dict] = []
    chart_type = "无"
    all_images: list[str] = []
    for turn_idx, turn in enumerate(turns, 1):
        q_text = turn["Q"]
        t0 = time.time()
        content = ""
        events = []
        # Single retry if bot returns the vikingbot fallback "I've completed
        # processing but have no response to give." This happens when the LLM
        # returns empty content mid-loop (transient gpt-5.4 proxy hiccup or a
        # complex multi-tool sequence that stalls). Retry with a fresh
        # sub-session so history state is reset.
        for attempt in range(2):
            attempt_session = session_id if attempt == 0 else f"{qid}-retry-{uuid.uuid4().hex[:6]}"
            try:
                resp = _chat(gateway, api_key, attempt_session, q_text)
                content = resp.get("message", "") or ""
                events = resp.get("events") or []
            except Exception as exc:
                print(f"[{qid}] turn {turn_idx} attempt {attempt+1} FAILED: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
                content = f"查询失败：{type(exc).__name__}: {str(exc)[:200]}"
                events = []
            # Retry on empty-response and loop-abort fallbacks; HTTP errors and
            # real clarifying content both count as a real outcome.
            if (
                "completed processing but have no response" not in content
                and "Aborted: detected a tool-call loop" not in content
            ):
                break
            if attempt == 0:
                print(f"[{qid}] turn {turn_idx} empty response — retrying once", flush=True)
        elapsed = time.time() - t0
        turn_sql = _extract_sql(events)
        turn_refs = _extract_references(events)
        turn_chart, turn_images = _extract_chart_info(events)
        all_sql.extend(turn_sql)
        all_refs.extend(turn_refs)
        if turn_chart != "无":
            chart_type = turn_chart
        # Rename bot-returned images to match 问题编号_顺序编号 scheme. The MCP
        # server returns chart_url like /charts/mcp_abc.jpg but the file is
        # actually at result/mcp_abc.jpg — translate.
        renamed_images: list[str] = []
        for img_url in turn_images:
            target = out_result_dir / f"{qid}_{turn_idx}.jpg"
            src_candidates = []
            if img_url.startswith("/charts/"):
                src_candidates.append(ROOT / "result" / Path(img_url).name)
            else:
                src_candidates.append(Path(img_url))
                src_candidates.append(ROOT / img_url.lstrip("/"))
            copied = False
            for src in src_candidates:
                if src.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(src, target)
                    copied = True
                    break
            if copied:
                # Emit a relative path from project root, for downstream result xlsx
                try:
                    rel = target.resolve().relative_to(ROOT.resolve())
                    renamed_images.append(f"./{rel}")
                except ValueError:
                    renamed_images.append(str(target))
        all_images.extend(renamed_images)
        # Build per-turn A
        if mode == "answer":
            A = {"content": content, "image": renamed_images}
        else:  # research (task 3) — also includes references
            A = {
                "content": content,
                "image": renamed_images,
                "references": turn_refs,
            }
        per_turn_payloads.append({"Q": q_text, "A": A})
        print(f"[{qid}] turn {turn_idx}/{len(turns)} done ({elapsed:.1f}s, sql={len(turn_sql)}, refs={len(turn_refs)}, img={len(renamed_images)})",
              flush=True)
    # Dedup SQL (keep first occurrence order)
    seen_sql = set()
    dedup_sql = []
    for s in all_sql:
        key = s.strip()
        if key in seen_sql:
            continue
        seen_sql.add(key)
        dedup_sql.append(s)
    return {
        "id": qid,
        "turns_input": turns,
        "answer_payloads": per_turn_payloads,
        "sql_joined": "\n\n".join(dedup_sql),
        "chart_type": chart_type,
    }


def _write_answer_xlsx(results: list[dict], path: Path) -> None:
    """Write result_2.xlsx — 附件7 表3 columns: 编号 / 问题 / SQL查询语句 / 图形格式 / 回答."""
    rows = []
    for r in results:
        rows.append({
            "编号": r["id"],
            "问题": json.dumps(r["turns_input"], ensure_ascii=False),
            "SQL查询语句": r["sql_joined"],
            "图形格式": r["chart_type"],
            "回答": json.dumps(r["answer_payloads"], ensure_ascii=False),
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False)


def _write_research_xlsx(results: list[dict], path: Path) -> None:
    """Write result_3.xlsx — 附件7 表6 columns: 编号 / 问题 / SQL查询语法 / 回答."""
    rows = []
    for r in results:
        rows.append({
            "编号": r["id"],
            "问题": json.dumps(r["turns_input"], ensure_ascii=False),
            "SQL查询语法": r["sql_joined"],
            "回答": json.dumps(r["answer_payloads"], ensure_ascii=False),
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["answer", "research"], required=True)
    parser.add_argument("--questions", required=True, help="Path to 附件4 or 附件6 xlsx")
    parser.add_argument("--output", required=True, help="result_2.xlsx or result_3.xlsx")
    parser.add_argument("--gateway", default=DEFAULT_GATEWAY)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--result-dir", default="result", help="Where chart images live")
    parser.add_argument("--limit", type=int, default=0, help="Process only first N questions (debug)")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="Dispatch N questions concurrently (each is an independent session). "
                             "4-8 is typically the sweet spot: gateway is async, LLM backend supports "
                             "concurrency up to its own cap, SQLite reads and MCP calls are safe in parallel.")
    args = parser.parse_args()

    questions_path = Path(args.questions)
    output_path = Path(args.output)
    result_dir = Path(args.result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)

    # Smoke: gateway reachable?
    try:
        health = requests.get(f"{args.gateway}/bot/v1/health", timeout=10)
        print(f"[health] {args.gateway} HTTP {health.status_code}")
    except Exception as exc:
        print(f"[fatal] gateway unreachable: {exc}")
        sys.exit(1)

    items = _load_questions_xlsx(questions_path)
    if args.limit > 0:
        items = items[: args.limit]
    print(f"[plan] processing {len(items)} question sets via {args.gateway}")

    def _run_one(item: dict) -> dict:
        try:
            return _bot_run_question(args.gateway, args.api_key, item, result_dir, args.task)
        except Exception as exc:
            print(f"[{item['id']}] FATAL: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
            return {
                "id": item["id"],
                "turns_input": item["turns"],
                "answer_payloads": [{"Q": t["Q"], "A": {"content": f"处理失败：{type(exc).__name__}", "image": [], **({"references": []} if args.task == "research" else {})}} for t in item["turns"]],
                "sql_joined": "",
                "chart_type": "无",
            }

    results: list[dict] = []
    t_start = time.time()
    if args.concurrency <= 1:
        for i, item in enumerate(items, 1):
            results.append(_run_one(item))
            print(f"[{i}/{len(items)}] {item['id']} done", flush=True)
    else:
        # Concurrent dispatch. Each question is an independent session — safe in parallel.
        # Preserve output order by sorting on the input items' index at the end.
        from concurrent.futures import ThreadPoolExecutor, as_completed
        id_to_index = {item["id"]: idx for idx, item in enumerate(items)}
        done_count = 0
        result_buf: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {pool.submit(_run_one, item): item for item in items}
            for fut in as_completed(futures):
                item = futures[fut]
                result_buf[item["id"]] = fut.result()
                done_count += 1
                print(f"[{done_count}/{len(items)}] {item['id']} done ({args.concurrency}x)", flush=True)
        results = [result_buf[item["id"]] for item in items]

    elapsed = time.time() - t_start
    if args.task == "answer":
        _write_answer_xlsx(results, output_path)
    else:
        _write_research_xlsx(results, output_path)
    print(f"[done] wrote {output_path} | {len(results)} rows | elapsed={elapsed:.1f}s")


if __name__ == "__main__":
    main()
