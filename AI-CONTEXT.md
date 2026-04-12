# AI-CONTEXT: 财报智能问数助手（泰迪杯 B 题）

## 项目简介

2026 泰迪杯 B 题，中药上市公司财报"智能问数"助手。三个任务：
- 任务一：PDF 财报 → 按官方 Schema 入库（4 张指定表）+ 数据校验
- 任务二：NL2SQL 智能问答 + 多轮对话 + 图表 → result_2.xlsx
- 任务三：研报 RAG + 归因分析 → result_3.xlsx

4.25 有 6 小时新数据测试，Pipeline 必须全自动。

## 技术栈

- Python 3.10+, LLM: OpenAI-compatible API (configured via env vars), Embedding: BAAI/bge-m3 (independent endpoint)
- 数据库: SQLite（Schema 对齐官方附件3 的 4 张表）
- PDF 解析: pdfplumber, 图表: matplotlib, UI: Gradio
- 创新点(P2): OpenViking 上下文记忆

## 数据

- 行业：中药上市公司（示例：华润三九 深交所 000999、金花股份 上交所 600080）
- 财报：2022-2025 年报/季报/半年报 PDF（39 份示例）
- 两种命名：深交所中文名、上交所 stock_code_date_random.pdf
- report_period 格式：2025Q3, 2022FY, 2024HY

## 官方 Schema（附件3，不可更改）

4 张表：core_performance_indicators_sheet, balance_sheet, income_sheet, cash_flow_sheet
共同字段：serial_number, stock_code, stock_abbr, report_period, report_year

## 目录结构

```
src/etl/        ← 任务一（pdf_parser, table_extractor, schema, validator, loader）
src/query/      ← 任务二（text2sql, conversation, chart, answer）
src/knowledge/  ← 任务三（research_loader, retriever, attribution）
src/llm/        ← LLM 客户端
src/viking/     ← OpenViking (P2)
src/prompts/    ← Prompt 模板
```
