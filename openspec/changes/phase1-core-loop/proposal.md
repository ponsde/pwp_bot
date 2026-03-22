## Why

泰迪杯 B 题要求从财报 PDF 中自动提取结构化数据入库（任务一），再基于数据库做 NL2SQL 智能问答（任务二）。任务一是整个系统的地基 —— 数据不准，后面全崩。4.25 还有 6 小时新数据测试，Pipeline 必须全自动化。Phase 1 聚焦任务一（ETL）+ 任务二的 NL2SQL 核心，先让系统能"解析-入库-答题"。

## What Changes

- 实现 PDF 财报自动解析：pdfplumber 提取表格，支持上交所/深交所两种命名格式
- 按官方 Schema（附件3）建库：4 张固定表（core_performance_indicators_sheet, balance_sheet, income_sheet, cash_flow_sheet）
- 表格字段映射：PDF 中文指标名 → 官方英文字段名
- 数据一致性校验：勾稽关系、跨表一致性、格式校验
- LLM 客户端封装：gpt-5.4 via OpenAI 兼容协议
- 两步式 NL2SQL：意图解析 → SQL 生成 → 执行 → 回答
- 多轮对话管理：处理追问式查询
- 可视化图表生成：matplotlib 折线图/柱状图/饼图
- 输出格式化：按附件7 格式生成 result_2.xlsx
- 基础 Gradio 界面
- 全自动 Pipeline 入口（pipeline.py）

## Capabilities

### New Capabilities

- `config`: 项目配置管理（API 密钥从环境变量读取，项目路径）
- `llm-client`: LLM API 客户端封装（chat completion + embedding + 重试）
- `pdf-parser`: PDF 财报解析（pdfplumber 表格提取，上交所/深交所两种格式）
- `table-extractor`: 表格字段映射（PDF 中文指标 → 官方 Schema 英文字段 + 单位换算）
- `schema`: 官方 Schema 建库（4 张表，字段类型对齐附件3）
- `validator`: 数据一致性校验（勾稽关系、跨表、格式）
- `loader`: 数据入库（校验通过后写入 SQLite）
- `text2sql`: 两步式 NL2SQL（意图解析 + SQL 生成 + 执行重试）
- `conversation`: 多轮对话管理（上下文保持、意图澄清）
- `chart`: 可视化图表生成（折线图/柱状图/饼图，存 result/ 目录）
- `answer-formatter`: 回答格式化输出（附件7 JSON 格式 + result_2.xlsx）
- `pipeline`: 全自动 Pipeline 入口（一键 ETL + 答题）
- `gradio-app`: Gradio 对话界面

### Modified Capabilities

（无既有能力）

## Impact

- **新增文件**：~20 个 Python 文件 + 6 个 Prompt 模板 + 配置文件
- **依赖**：pdfplumber, openai, gradio, matplotlib, pandas, openpyxl, python-dotenv
- **外部服务**：LLM API (oai.whidsm.cn)
- **数据**：SQLite 数据库（官方 Schema 4 张表）、result/ 图表图片、result_2.xlsx
