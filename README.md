# PWP Bot - 中药上市公司财报智能问数助手

2026 泰迪杯数据挖掘挑战赛 B 题参赛作品。从 PDF 财务报告中自动提取结构化数据，支持自然语言问答和图表生成。

## 三个任务

| 任务 | 描述 | 入口 |
|------|------|------|
| 任务一 | PDF 财报 → SQLite 四张官方指定表（ETL） | `pipeline.py --task etl` |
| 任务二 | NL2SQL 智能问答 + 多轮对话 + 图表 | `pipeline.py --task answer` |
| 任务三 | 研报 RAG + 归因分析 | TBD |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY

# 3. 准备数据
# 将附件1/2/3 放入 data/sample/示例数据/ 目录

# 4. 运行 ETL
python3 pipeline.py --task etl \
  --db-path data/db/finance.db \
  --input "data/sample/示例数据/附件2：财务报告"

# 5. 数据质量检查
PYTHONPATH=. python3 scripts/etl_quality_check.py data/db/finance.db

# 6. 运行问答
python3 pipeline.py --task answer \
  --db-path data/db/finance.db \
  --questions <questions.xlsx> \
  --output result_2.xlsx

# 7. 启动 Web UI（FastAPI + web-studio SPA，见 backend/README.md）
uvicorn backend.server:app --host 0.0.0.0 --port 8000
```

## 项目结构

```
src/
  etl/                  # 任务一：PDF → SQLite
    pdf_parser.py       #   PDF 解析（深交所/上交所两种格式）
    table_extractor.py  #   表格提取 + 字段映射 + 派生计算
    schema.py           #   官方 schema 管理（附件3）
    validator.py        #   数据校验
    loader.py           #   加载入库 + YoY 后处理 + fallback 补全
  query/                # 任务二：NL2SQL 问答
    text2sql.py         #   意图分析 → SQL 生成 → 三层恢复
    chart.py            #   图表类型选择 + matplotlib 生成
    conversation.py     #   多轮对话 slot 管理
  llm/
    client.py           #   OpenAI 兼容 LLM 客户端
  prompts/              #   Prompt 模板（seek_table, generate_sql 等）
scripts/
  etl_quality_check.py  # 数据质量自检（值域/跨表一致性/YoY 校验/覆盖率）
tests/                  # pytest 测试（无需 LLM API）
pipeline.py             # 主入口（ETL / 答题）
backend/                # FastAPI 服务（给 web-studio SPA 提供 /api/ask 等）
web-studio/             # React 前端（vendored from Ferry-200/OpenViking new-frontend）
config.py               # 配置加载
```

## 数据库 Schema

四张官方指定表（由附件3定义）：

| 表名 | 内容 |
|------|------|
| `core_performance_indicators_sheet` | 主要会计数据和财务指标 |
| `balance_sheet` | 合并资产负债表 |
| `income_sheet` | 合并利润表 |
| `cash_flow_sheet` | 合并现金流量表 |

`report_period` 格式：`2025Q3`、`2022FY`、`2024HY`

## ETL 数据质量

当前样本数据（2 家公司 x 12 期）质量：

- 自检 issues：**0**
- 核心字段覆盖率：**100%**（eps, revenue, profit, roe 等）
- YoY 字段：**66.67%**（理论上限，无 2021 年数据）
- 加权 ROE（扣非）：**83.33%**

## 测试

```bash
# 全部测试（无需 LLM API）
python3 -m pytest tests/ -v

# 单独测试
python3 -m pytest tests/test_text2sql.py -v
python3 -m pytest tests/test_etl_quality_check.py -v
```

## 环境变量

**助手自己的 LLM**（Text2SQL / 路由分类 / 回答生成）
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_API_KEY` | (必填) | 主 LLM 密钥 |
| `LLM_API_BASE` | (必填) | 主 LLM OpenAI 兼容基础 URL |
| `LLM_MODEL` | (必填) | 主 LLM 模型名 |
| `LLM_TIMEOUT` | `60` | LLM 请求超时（秒） |
| `SQLITE_DB_PATH` | `data/db/finance.db` | SQLite 数据库路径 |

**OpenViking**（研报 RAG，独立命名空间）
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OV_EMBEDDING_API_KEY` | (RAG 必填) | OV embedding 服务密钥 |
| `OV_EMBEDDING_API_BASE` | (RAG 必填) | OV embedding 基础 URL |
| `OV_EMBEDDING_MODEL` | (RAG 必填) | OV embedding 模型名 |
| `OV_EMBEDDING_DIMENSION` | (RAG 必填) | OV embedding 维度，必须与模型一致（如 bge-m3=1024） |
| `OV_VLM_API_KEY` | (摘要必填) | OV VLM 密钥（生成 L0/L1 摘要 + 图像解析，需识图能力） |
| `OV_VLM_API_BASE` | (摘要必填) | OV VLM 基础 URL |
| `OV_VLM_MODEL` | (摘要必填) | OV VLM 模型名（如 gpt-4o / claude-3.5-sonnet） |
