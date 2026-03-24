# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

2026 泰迪杯 B 题：中药上市公司财报"智能问数"助手。三个任务：
- **任务一**: PDF 财报 → SQLite 四张官方指定表（ETL）
- **任务二**: NL2SQL 智能问答 + 多轮对话 + 图表 → result_2.xlsx
- **任务三**: 研报 RAG + 归因分析 → result_3.xlsx

关键约束：4.25 有 6 小时新数据测试，Pipeline 必须全自动。

## Commands

```bash
# Run all tests (exclude reference code)
python3 -m pytest tests/ -v

# Run a single test
python3 -m pytest tests/test_text2sql.py::test_text2sql_query_success_with_conversation -v

# Run ETL pipeline (PDF → SQLite)
python3 pipeline.py --task etl --db-path data/db/finance.db --input data/sample/示例数据/附件2：财务报告

# Run answer pipeline (questions → result xlsx)
python3 pipeline.py --task answer --db-path data/db/finance.db --questions <questions.xlsx> --output result_2.xlsx

# Launch Gradio UI
python3 app.py
```

## Environment Setup

Copy `.env.example` to `.env` and fill in `LLM_API_KEY`. Config is loaded via `config.py` → `load_settings()`.

Key env vars: `LLM_API_KEY`, `LLM_API_BASE` (default: oai.whidsm.cn/v1), `LLM_MODEL` (default: gpt-5.4), `SQLITE_DB_PATH`.

## Architecture

### Data Flow

```
PDF files → PDFParser → TableExtractor → DataValidator → ETLLoader → SQLite
Question  → Text2SQLEngine.analyze() → generate_sql() → execute → answer/chart
```

### Two-Step Text2SQL with Three-Layer Recovery

`src/query/text2sql.py` — the core query engine:
1. **analyze()**: Intent extraction — identifies companies, fields, periods, tables from NL question. Uses `seek_table.md` prompt or heuristic fallback (no LLM).
2. **generate_sql()**: SQL generation from intent + schema. Uses `generate_sql.md` prompt or heuristic fallback.
3. **query()**: Orchestrates the full flow with three recovery layers:
   - Layer 1: SQL syntax/execution errors → regenerate SQL
   - Layer 2: Result validation (`validate_result.md`) → regenerate if results look wrong
   - Layer 3: Reflection (`reflect.md`) → re-analyze intent from scratch

Both `analyze()` and `generate_sql()` have dual paths: LLM-powered (via prompts) and heuristic fallback (no API needed, used in tests).

### ETL Pipeline

`src/etl/` — PDF parsing and structured data extraction:
- `pdf_parser.py`: Extracts metadata (stock_code, report_period) from both 深交所 (Chinese title) and 上交所 (filename-based) PDF formats. Detects summary reports (摘要) to skip.
- `table_extractor.py`: Finds financial tables by title patterns, extracts key-value pairs using pdfplumber, handles cross-page table merging.
- `schema.py`: Reads official schema from `附件3` Excel, creates SQLite tables, provides field metadata. The 4 tables share common key fields (serial_number, stock_code, stock_abbr, report_period, report_year).
- `validator.py`: Validates extracted data against schema before loading.
- `loader.py`: Orchestrates parse → extract → validate → INSERT OR REPLACE into SQLite.

### Prompt Templates

`src/prompts/*.md` — loaded via `load_prompt(template_name, **variables)` using Python `str.format`. Templates: `seek_table.md`, `generate_sql.md`, `clarify.md`, `chart_select.md`, `answer.md`, `reflect.md`, `validate_result.md`.

### Multi-Turn Conversation

`src/query/conversation.py` — `ConversationManager` tracks dialogue history and slot state (companies, fields, periods, tables). Supports slot merging across turns and missing-slot detection for clarification.

### LLM Client

`src/llm/client.py` — OpenAI-compatible client with retry logic. `json_mode` auto-extracts JSON from LLM responses (handles markdown code blocks). Instantiated via `LLMClient.from_env()`.

## Schema Constraints

The 4 database tables are defined by the official competition attachment (附件3) — **do not modify the schema**. Table names: `core_performance_indicators_sheet`, `balance_sheet`, `income_sheet`, `cash_flow_sheet`.

`report_period` format: `2025Q3`, `2022FY`, `2024HY` (standardized from Chinese period names).

## Data Paths

- Sample PDFs: `data/sample/示例数据/附件2：财务报告/`
- Schema Excel: `data/sample/示例数据/附件3：数据库-表名及字段说明.xlsx`
- Company list: `data/sample/示例数据/附件1：中药上市公司基本信息（截至到2025年12月22日）.xlsx`
- SQLite DB: `data/db/finance.db` (pipeline output)
- Results: `result/` directory

## Testing Notes

- Tests use heuristic fallbacks (no LLM API needed) by passing `llm_client=None` to `Text2SQLEngine`.
- `tests/test_etl_phase1.py` contains integration tests that process actual sample PDFs — these require the sample data to be present.
- `references/` contains third-party reference code (FinGLM competition entries, chatbot_financial_statement) — not part of this project, ignore for testing.
