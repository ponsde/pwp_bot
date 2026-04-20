# 上市公司财报"智能问数"助手

面向中药行业上市公司财报的自然语言问答系统：自动从 PDF 财报抽取结构化数据、用自然语言回答财务问题并自动生成图表，同时通过研究报告检索补充归因分析。

## 能做什么

- **PDF → SQLite ETL**：把上交所 / 深交所两种格式的财报 PDF 批量抽取为四张结构化表（核心业绩指标、资产负债、利润、现金流）。
- **Text2SQL 智能问答**：自然语言问句 → 意图抽取 → SQL 生成 → SQLite 执行 → 可视化图表，支持多轮对话与意图澄清，带三层错误恢复（SQL 语法、结果越界、反思重分析）。
- **研报 RAG 归因**：基于 OpenViking 向量库检索研究报告，对"为什么 / 政策 / 战略"类问题给出带参考文献的答案。
- **Web UI**：React SPA，带流式打字机效果、MCP 工具调用可视化、参考文献卡片、回答重试与版本切换。

## 架构概览

```
     浏览器 (web-studio SPA)
        │ /api/*  /bot/v1/*
        ▼
     FastAPI (backend/server.py, :8080)
        │
        ├── /api/chat/*       SQLite 会话持久化
        ├── /charts/*         图表静态
        ├── /papers/*         研报 PDF 静态
        └── /bot/v1/*    ──▶  vikingbot gateway (:18790)
                                    │
                                    ├── MCP stdio ──▶ backend/taidi_mcp_server.py
                                    │                   │
                                    │                   └── src/query/text2sql.py
                                    │                       src/query/chart.py
                                    │                       (SQLite 查询 + 折线/柱状/饼图)
                                    │
                                    └── HTTP ──────▶ openviking-server (:18792)
                                                    (向量检索 + 研报摘要)
```

## 运行环境

- Python 3.12+
- Node.js 20+（仅当需要重建前端）
- SQLite（随 Python 内置）
- OpenAI 兼容的 LLM 端点（用于意图抽取 / SQL 生成 / 回答整合 / 归因判读）
- 可选：独立的 embedding + VLM 端点供研报 RAG 使用

## 快速开始

### 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 应用 vikingbot 流式补丁（OpenViking 的 PR #13 + #23，未进 PyPI release）
bash scripts/bot_streaming_patches/apply.sh
```

### 2. 配置密钥

```bash
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY / LLM_API_BASE / LLM_MODEL 等
cp ov.conf.example ov.conf
# 编辑 ov.conf 同步相同的 API key
```

### 3. 使用预置数据

仓库已内置：

- `data/db/finance.db` —— 72 家公司 × 12 期 × 4 张表的 SQLite 库（ETL 输出产物）
- `.openviking/` —— 研报向量索引（532 篇研报切片 + abstract + embedding）

可以直接跳到第 5 步使用。

### 4. （可选）重跑 ETL 或重建 RAG

```bash
# 把 PDF 重新入库（当你有新的财报 PDF 时）
python3 pipeline.py --task etl \
    --db-path data/db/finance.db \
    --input data/sample/示例数据/附件2：财务报告

# 研报向量索引重建（当你有新的研报 PDF 时）
python3 scripts/index_research.py  data/sample/示例数据/附件5：研报数据
```

### 5. 启动服务

三个进程，各用一个终端（或 systemd / pm2）：

```bash
# 终端 A —— OpenViking 向量服务（18792）
.venv/bin/openviking-server --config ov.conf --host 127.0.0.1 --port 18792

# 终端 B —— vikingbot agent 网关（18790）
.venv/bin/python -m vikingbot gateway --port 18790 -c ov.conf

# 终端 C —— FastAPI + 前端 SPA（8080）
.venv/bin/uvicorn backend.server:app --host 0.0.0.0 --port 8080
```

浏览器打开 `http://localhost:8080/`。

### 6. 或者：批量跑问题集

```bash
# 任务二：针对结构化数据的问答
python3 pipeline.py --task answer \
    --db-path data/db/finance.db \
    --questions 问题汇总.xlsx \
    --output result_2.xlsx

# 任务三：融合研报 RAG 的归因问答
python3 pipeline.py --task research \
    --db-path data/db/finance.db \
    --questions 问题汇总.xlsx \
    --output result_3.xlsx
```

## 目录结构

```
src/
├── etl/          # PDF → SQLite 的 5 个模块
├── query/        # Text2SQL + 多轮对话 + 图表
├── knowledge/    # 研报 RAG 引擎
├── llm/          # OpenAI 兼容客户端
├── audit/        # 答案质量审计（数字一致性、引用校验、LLM-as-judge）
└── prompts/      # seek_table / generate_sql / clarify / answer / reflect / ...

backend/
├── server.py            # FastAPI 主服务，端口 8080
├── chat_store.py        # SQLite 会话持久化
└── taidi_mcp_server.py  # MCP 工具服务器（暴露 mcp_fin_query 等给 bot）

web-studio/
├── src/                 # Vite + React + TanStack Router 前端源码
└── dist/                # 构建产物（git 不追踪，由 npm run build 生成）

scripts/
├── bot_streaming_patches/  # vikingbot 流式 SSE 的 monkey patch
├── audit_results.py        # 结果 xlsx 的自动审计
├── fix_audit_findings.py   # 审计后自动清理 / 重写
├── index_research.py       # 研报批量入库
├── regen_charts.py         # 根据 xlsx 重新渲染图表
└── ...

tests/                      # pytest（无需 LLM API，用启发式 fallback）
pipeline.py                 # CLI 主入口：--task etl|answer|research
config.py                   # 环境变量读取
Dockerfile                  # 一键构建包含 OV + bot + backend 的镜像
railway.json                # Railway 部署配置
```

## 数据库 Schema

四张表，字段以官方口径为准：

| 表 | 内容 |
| :-- | :-- |
| `core_performance_indicators_sheet` | 核心业绩指标（营收、利润、每股收益等） |
| `balance_sheet` | 合并资产负债表 |
| `income_sheet` | 合并利润表 |
| `cash_flow_sheet` | 合并现金流量表 |

所有表共用字段：`serial_number`, `stock_code`, `stock_abbr`, `report_period`, `report_year`。
`report_period` 标准化格式：`2025Q3`、`2022FY`（年度）、`2024HY`（半年度）。

## 测试

```bash
# 纯逻辑测试（启发式 fallback，不调 LLM）
python3 -m pytest tests/ --ignore=tests/test_etl_phase1.py -v

# 端到端 ETL 集成测试（处理 data/sample/ 下的真实 PDF）
python3 -m pytest tests/test_etl_phase1.py -v

# 审计模块单元测试
python3 -m pytest tests/audit/ -v
```

## 关键环境变量

**LLM**（意图抽取 / SQL 生成 / 回答整合，OpenAI 兼容）

| 变量 | 说明 |
| :-- | :-- |
| `LLM_API_KEY` | LLM 密钥 |
| `LLM_API_BASE` | base URL，如 `https://api.openai.com/v1` |
| `LLM_MODEL` | 模型名，如 `gpt-4o` |
| `LLM_TIMEOUT` | 请求超时秒数，默认 60 |
| `SQLITE_DB_PATH` | SQLite 路径，默认 `data/db/finance.db` |

**OpenViking / 研报 RAG**（独立命名空间，与助手 LLM 互不影响）

| 变量 | 说明 |
| :-- | :-- |
| `OV_EMBEDDING_API_KEY` / `_BASE` / `_MODEL` / `_DIMENSION` | embedding 端点（如 BAAI/bge-m3 ≡ 1024 维） |
| `OV_VLM_API_KEY` / `_BASE` / `_MODEL` | VLM 端点（生成研报摘要 + 图像抽取，需识图能力） |

## 容器化

```bash
# 构建镜像（含 OV + bot + backend + 前端 dist）
docker build -t finance-qa .

# 运行（-p 暴露对应端口）
docker run -p 8080:8080 --env-file .env finance-qa
```

`railway.json` 可一键推到 Railway 上。
