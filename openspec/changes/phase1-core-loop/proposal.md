## Why

泰迪杯比赛（截止 2026-04-24）要求构建财报智能问答助手。Phase 1 的目标是打通核心闭环：用户提问 → 系统从结构化财务数据中查询 → 返回准确答案。这是整个系统的基础，后续的 RAG、OV 记忆、联想推荐都建立在这个闭环之上。现在开始是因为只剩 33 天，Phase 1 需要在两周内完成。

## What Changes

- 新建项目基础设施：配置管理、LLM 客户端封装
- 构建 ETL 数据管线：通过 AKShare API 批量拉取 A 股上市公司财务数据，清洗后入库 SQLite
- 构建 PDF 解析管线：用 pdfplumber 提取年报全文文本，导入 OpenViking Resource（为 Phase 2 RAG 做准备）
- 实现两步式 Text2SQL 查询引擎：Step1 意图提取（公司/指标/年份）→ Step2 生成 SQL → 执行 → 回答
- 搭建基础 Gradio 对话界面
- 部署 OpenViking（embedded 模式），验证 Resource 导入和 find 检索

## Capabilities

### New Capabilities

- `config`: 项目配置管理（API endpoint、模型名、数据库路径，从环境变量读取密钥）
- `llm-client`: LLM API 客户端封装（兼容 OpenAI 协议，支持 chat completion 和 embedding）
- `etl-pipeline`: ETL 数据管线（AKShare 拉取财务三表 → 清洗标准化 → SQLite 垂直表入库）
- `pdf-parser`: PDF 年报解析（pdfplumber 提取全文文本，不抠表格数字）
- `text2sql`: 两步式 Text2SQL 查询引擎（意图提取 → SQL 生成 → 执行 → 失败重试）
- `prompt-templates`: Prompt 模板管理（seek_database、generate_sql、answer 三个核心模板）
- `ov-resource`: OpenViking Resource 管理（部署配置、年报全文导入、find 检索验证）
- `gradio-app`: Gradio 对话界面（最小可用：输入问题 → 显示回答）

### Modified Capabilities

（无既有能力）

## Impact

- **新增文件**：~15 个 Python 文件 + 4 个 Prompt 模板 + 配置文件
- **依赖**：akshare, pdfplumber, openai, gradio, openviking
- **外部服务**：LLM API (oai.whidsm.cn)、Embedding API (同源)
- **数据**：SQLite 数据库（全 A 股 3 年财务数据，预估几百 MB）、OV 本地存储
