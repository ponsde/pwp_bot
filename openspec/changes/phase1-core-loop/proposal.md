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

## Capability Scope Clarification

经实测示例 PDF 与附件3 后，Phase 1 的实现边界需要进一步明确：

- PDF 抽取主路径应以 **规则 + pdfplumber** 为主，不应把 LLM fallback 设为默认在线依赖。
- 上交所 `stock_code_date_random.pdf` 不能仅靠发布日期推断报告类型；必须优先解析 PDF 首页标题。
- 只应对 **完整版报告** 入库，`摘要` 文件默认跳过。
- `report_period` 的统一格式应为完整值：`2023FY / 2024Q1 / 2024HY / 2025Q3`。
- 附件3 的字段单位 **并不统一**，必须按字段逐项转换，不能概括为“PDF 元 → Schema 万元”。
- `core_performance_indicators_sheet` 不是三大报表的简单别名，需要单独从“主要会计数据和财务指标”等章节抽取，并对同比/环比字段做计算。

## Capabilities

### New Capabilities

- `config`: 项目配置管理（API 密钥从环境变量读取，项目路径）
- `llm-client`: LLM API 客户端封装（chat completion + embedding + 重试）
- `pdf-parser`: PDF 财报解析（pdfplumber 表格提取，上交所/深交所两种格式）
- `table-extractor`: 表格字段映射（PDF 中文指标 → 官方 Schema 英文字段 + 字段级单位换算）
- `schema`: 官方 Schema 建库（4 张表，字段类型对齐附件3）
- `validator`: 数据一致性校验（勾稽关系、跨表、格式）
- `loader`: 数据入库（校验通过后写入 SQLite）
- `text2sql`: 两步式 NL2SQL（意图解析 + SQL 生成 + 执行重试）
- `conversation`: 多轮对话管理（上下文保持、意图澄清）
- `chart`: 可视化图表生成（折线图/柱状图/饼图，存 result/ 目录）
- `answer-formatter`: 回答格式化输出（附件7 JSON 格式 + result_2.xlsx）
- `pipeline`: 全自动 Pipeline 入口（一键 ETL + 答题）
- `gradio-app`: Gradio 对话界面

### Modified Capability Expectations

- `pdf-parser`：
  - 深交所可直接从文件名解析公司简称与报告类型。
  - 上交所必须优先从首页标题识别“年度报告 / 第一季度报告 / 半年度报告 / 第三季度报告 / 摘要”。
- `table-extractor`：
  - 需要分别支持三大报表和“主要会计数据/主要财务指标”区块。
  - 需要支持同比、环比、占比等派生字段计算。
- `loader`：
  - 应显式跳过摘要 PDF。
- `text2sql`：
  - SQL 条件中的 `report_period` 应直接使用完整标准值，如 `2025Q3`。

## Impact

- **新增文件**：~20 个 Python 文件 + 6 个 Prompt 模板 + 配置文件
- **依赖**：pdfplumber, openai, gradio, matplotlib, pandas, openpyxl, python-dotenv
- **外部服务**：LLM API (oai.whidsm.cn)
- **数据**：SQLite 数据库（官方 Schema 4 张表）、result/ 图表图片、result_2.xlsx

## Validation Notes

本 proposal 已基于示例数据进行可实现性复核：

- 深交所样例 `华润三九：2023年年度报告.pdf` 中，pdfplumber 可直接抽出：
  - 主要会计数据/主要财务指标
  - 合并资产负债表
  - 合并利润表
  - 合并现金流量表
- 上交所样例 `600080_20240427_0WKP.pdf` 中，pdfplumber 可直接抽出同类关键表。
- 上交所同一日期存在多份不同类型 PDF（报告、摘要、季报），故“按日期推断类型”不是安全实现前提。
