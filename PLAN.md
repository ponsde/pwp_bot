# 财报"智能问数"助手 — 项目计划

## 项目信息

- **比赛**: 2026 泰迪杯 B 题
- **截止**: 2026-04-24 提交作品；2026-04-25 09:00-15:00 测试新数据（6小时）
- **起始**: 2026-03-22
- **可用时间**: ~33 天（实际投入约 50%）
- **LLM API**: OpenAI 兼容协议（endpoint 和 model 通过环境变量配置）
- **Embedding**: BAAI/bge-m3（独立 endpoint，via 环境变量）
- **创新点**: OpenViking 上下文记忆系统
- **行业**: 中药上市公司（示例数据：华润三九、金花股份）

---

## 赛题分析

### 三个任务

| 任务 | 核心内容 | 输入 | 输出 |
|------|---------|------|------|
| **任务一** | PDF 财报 → 结构化数据库 + 自动校验 | 附件2 PDF | SQLite 四张表 |
| **任务二** | 智能问数（NL2SQL + 多轮对话 + 图表） | 附件4 问题 | result_2.xlsx + 图片 |
| **任务三** | 知识库增强（研报RAG + 多意图 + 归因） | 附件6 问题 | result_3.xlsx + 图片 |

### 关键约束

```
1. Schema 是官方指定的（附件3），不需要自己设计！
   → 4 张表：core_performance_indicators_sheet
              balance_sheet
              income_sheet
              cash_flow_sheet

2. 4.25 测试给新数据，6小时内出结果
   → Pipeline 必须全自动化

3. 输出格式严格（附件7）
   → JSON 格式回答 + SQL 语句 + 图表图片 + 参考文献

4. 任务三需要研报知识库（附件5）
   → RAG 不是可选的，是必做的

5. 问题是多轮对话格式
   → [{"Q": "问题1"}, {"Q": "追问"}]
```

### 优先级排序

```
🔴 P0 — 必须做好（决定生死）
   ├── PDF 自动解析 → 按官方 Schema 入库（任务一）
   ├── 数据一致性校验（任务一明确要求）
   ├── NL2SQL 准确率（任务二核心）
   └── 全自动化 Pipeline（4.25 测试用）

🟡 P1 — 应该做好（决定分数）
   ├── 研报知识库 RAG + 归因（任务三）
   ├── 多轮对话 / 意图澄清（任务二）
   ├── 多意图拆解与规划（任务三）
   └── 可视化图表生成（任务二、三）

🟢 P2 — 锦上添花（拉开差距）
   ├── OpenViking 记忆增强（创新点 + 论文亮点）
   ├── 联想推荐
   └── 界面美观度
```

---

## 架构设计

### 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                       Gradio UI                               │
│  对话界面 │ 图表展示 │ 归因溯源面板 │ 记忆可视化（P2）         │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                      Orchestrator                             │
│                                                               │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ OV 上下文 │──▶│ 意图识别  │──▶│ 查询路由  │──▶│ 回答生成  │  │
│  │ 增强(P2) │   │ + 多意图  │   │ + 多轮   │   │ + 图表   │  │
│  │          │   │   拆解    │   │   管理   │   │ + 归因   │  │
│  └──────────┘   └──────────┘   └────┬─────┘   └──────────┘  │
│                                     │                         │
└─────────────────────────────────────┼─────────────────────────┘
              ┌───────────────────────┼───────────────┐
              ▼                       ▼               ▼
  ┌─────────────────┐   ┌──────────────────┐   ┌──────────────────────┐
  │  精确查询引擎     │   │  知识库检索引擎    │   │  上下文记忆引擎       │
  │  (Text2SQL)      │   │  (RAG)           │   │  (OpenViking) ★ P2   │
  │                  │   │                  │   │                      │
  │  NL → SQL        │   │  研报 + 财报原文  │   │  用户画像 / 偏好      │
  │  SQL → 执行      │   │  Embed → 召回    │   │  查询案例 / 模式      │
  │  结果 → 图表     │   │  Rerank → 精排   │   │  Session → commit    │
  │                  │   │  归因溯源         │   │  记忆自迭代           │
  │  SQLite          │   │  FAISS/OV find   │   │                      │
  └─────────────────┘   └──────────────────┘   └──────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                       ETL 数据处理层                           │
│                                                               │
│  财报 PDF → pdfplumber → 表格提取 → 校验 → SQLite 入库        │
│          → 文本分块 → Embedding → 向量索引                     │
│                                                               │
│  研报 PDF → 文本提取 → 分块 → Embedding → 向量索引（任务三）    │
│          → 元信息入库（来源、标题、日期）→ 归因用               │
│                                                               │
│  财报全文 → OpenViking Resource（P2）                          │
└──────────────────────────────────────────────────────────────┘
```

### 官方 Schema（附件3 指定，不可更改）

```sql
-- 4 张表，字段已由比赛方定义

core_performance_indicators_sheet  -- 核心业绩指标（EPS、营收、净利润、ROE...）
balance_sheet                       -- 资产负债表（货币资金、应收、存货、总资产...）
income_sheet                        -- 利润表（净利润、营业收入、费用明细...）
cash_flow_sheet                     -- 现金流量表（经营/投资/融资 三类现金流）

-- 共同字段：stock_code, stock_abbr, report_period, report_year
-- report_period 格式：FY=年报, Q1=一季, HY=半年, Q3=三季
```

### Text2SQL 策略

Schema 固定 4 张表，两步策略简化为：

```
用户问题: "金花股份利润总额是多少" → "2025年第三季度的"

Step 1 — 意图解析 + 表/字段选择
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  输入: 用户问题（含多轮上下文）
  LLM 输出:
    {
      "tables": ["income_sheet"],
      "fields": ["total_profit"],
      "companies": ["金花股份"],
      "periods": ["2025Q3"]
    }

Step 2 — 生成 SQL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  输入: Step1 结果 + 表 Schema + 示例数据
  LLM 输出:
    SELECT total_profit
    FROM income_sheet
    WHERE stock_abbr = '金花股份'
      AND report_period = 'Q3'
      AND report_year = 2025;

Step 3 — 执行 + 回答 + 图表
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  执行 SQL → 格式化结果 → LLM 生成分析结论
  如需图表 → matplotlib/plotly 生成 → 存入 result/
  SQL 报错 → 反馈 LLM 重试（最多 2 次）
```

### 输出格式（附件7 严格要求）

任务二输出 result_2.xlsx：
```json
{
  "编号": "B1001",
  "问题": [{"Q": "金花股份利润总额是多少"}, {"Q": "2025年第三季度的"}],
  "SQL查询语句": "SELECT total_profit FROM income_sheet WHERE ...",
  "回答": [
    {"Q": "金花股份利润总额是多少", "A": {"content": "请问你查询哪一个报告期的利润总额？"}},
    {"Q": "2025年第三季度的", "A": {"content": "金花股份2025年第三季度的利润总额是3140万元。"}}
  ]
}
```

任务三输出 result_3.xlsx（增加 references）：
```json
{
  "A": {
    "content": "回答内容",
    "image": ["./result/B2003_1.jpg"],
    "references": [
      {
        "paper_path": "./附件5：研报数据/行业研报/xxx.pdf",
        "text": "参考文献原文摘要",
        "paper_image": "参考文献图表路径"
      }
    ]
  }
}
```

---

## 项目结构

```
taidi_bei/
├── PLAN.md                       ← 本文件
├── AI-CONTEXT.md                 ← Agent 共享项目背景
│
├── src/
│   ├── __init__.py
│   │
│   ├── etl/                      ← 任务一：PDF → 结构化数据库
│   │   ├── __init__.py
│   │   ├── pdf_parser.py         ← PDF 解析（pdfplumber）
│   │   ├── table_extractor.py    ← 表格提取与清洗
│   │   ├── schema.py             ← 官方 Schema 定义（4 张表）
│   │   ├── validator.py          ← 数据一致性校验
│   │   └── loader.py             ← 数据入库
│   │
│   ├── query/                    ← 任务二：智能问数
│   │   ├── __init__.py
│   │   ├── intent.py             ← 意图识别 + 多意图拆解
│   │   ├── text2sql.py           ← NL2SQL 核心
│   │   ├── conversation.py       ← 多轮对话管理
│   │   ├── chart.py              ← 图表生成（matplotlib/plotly）
│   │   └── answer.py             ← 回答生成 + 格式化输出
│   │
│   ├── knowledge/                ← 任务三：知识库增强
│   │   ├── __init__.py
│   │   ├── research_loader.py    ← 研报数据导入
│   │   ├── retriever.py          ← RAG 检索（FAISS/OV find）
│   │   └── attribution.py        ← 归因分析 + 溯源
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py             ← LLM API 封装
│   │
│   ├── viking/                   ← OpenViking 集成（P2 创新点）
│   │   ├── __init__.py
│   │   ├── client.py             ← OV 客户端
│   │   ├── resource.py           ← Resource 管理
│   │   ├── session.py            ← Session + 记忆提取
│   │   └── context.py            ← 上下文增强 + 联想推荐
│   │
│   └── prompts/
│       ├── intent.md             ← 意图识别
│       ├── seek_table.md         ← Step1: 选表选字段
│       ├── generate_sql.md       ← Step2: 生成 SQL
│       ├── answer.md             ← 回答生成
│       ├── clarify.md            ← 意图澄清引导
│       └── chart_select.md       ← 图表类型选择
│
├── pipeline.py                   ← 全自动 Pipeline 入口（4.25 测试用）
├── app.py                        ← Gradio 交互界面
├── config.py                     ← 配置管理
├── ov.conf                       ← OpenViking 配置
│
├── data/
│   ├── sample/示例数据/           ← 官方示例数据（已解压）
│   │   ├── 附件1：中药上市公司基本信息.xlsx
│   │   ├── 附件2：财务报告/       ← PDF 年报
│   │   ├── 附件3：数据库-表名及字段说明.xlsx
│   │   ├── 附件4：问题汇总.xlsx   ← 任务二问题
│   │   ├── 附件5：研报数据/       ← 任务三知识库
│   │   └── 附件6：问题汇总.xlsx   ← 任务三问题
│   ├── db/                       ← SQLite 数据库文件
│   └── vectors/                  ← 向量索引
│
├── result/                       ← 输出结果（图表图片）
├── result_2.xlsx                 ← 任务二输出
├── result_3.xlsx                 ← 任务三输出
│
├── tests/
│   ├── test_pdf_parser.py
│   ├── test_text2sql.py
│   ├── test_viking.py
│   └── test_pipeline.py          ← 全流程测试
│
├── evaluate/
│   └── benchmark.py
│
├── references/                   ← 参考项目
│   ├── chatbot_financial_statement/
│   ├── FinGLM/
│   └── OpenViking-examples/
│
├── docs/paper/                   ← 论文
└── requirements.txt
```

---

## 分阶段计划

### Phase 1 — 任务一：PDF 解析 + 数据库（P0）

**目标**: 财报 PDF → 按官方 Schema 入库 SQLite + 数据校验
**时间**: Week 1-2 前半（3.22 — 3.31）

| 任务 | 关键参考 | 产出 |
|------|----------|------|
| 环境搭建 + 依赖安装 | — | requirements.txt |
| 官方 Schema 实现 | 附件3 xlsx | `etl/schema.py` |
| PDF 解析（深交所格式） | FinGLM 馒头科技 | `etl/pdf_parser.py` |
| PDF 解析（上交所格式） | FinGLM 南哪都队 | 同上 |
| 表格提取与字段映射 | 附件3 字段定义 | `etl/table_extractor.py` |
| 数据一致性校验 | 赛题要求 | `etl/validator.py` |
| 自动入库 | — | `etl/loader.py` |
| LLM API 接入 | — | `llm/client.py` |
| OpenViking 部署 | OV examples | `ov.conf` |

**完成标准**:
- 华润三九 + 金花股份的所有财报 PDF 自动解析入库
- 4 张表数据完整，校验通过
- `python pipeline.py --task etl --input data/sample/` 一键完成

### Phase 2 — 任务二：智能问数（P0）

**目标**: NL2SQL + 多轮对话 + 图表 → 输出 result_2.xlsx
**时间**: Week 2 后半 — Week 3（4.01 — 4.08）

| 任务 | 关键参考 | 产出 |
|------|----------|------|
| 意图识别 | — | `query/intent.py` |
| NL2SQL 两步策略 | chatbot_financial_statement | `query/text2sql.py` |
| 多轮对话管理 | 附件4 问题格式 | `query/conversation.py` |
| 意图澄清机制 | 赛题要求 | `prompts/clarify.md` |
| 图表生成 | — | `query/chart.py` |
| 回答格式化输出 | 附件7 格式 | `query/answer.py` |
| Prompt 模板 v1 | chatbot_financial_statement | `prompts/*.md` |
| Gradio 基础界面 | — | `app.py` |

**完成标准**:
- 附件4 的 2 个示例问题能正确回答
- 输出符合附件7 格式的 result_2.xlsx
- 能处理多轮对话（追问）

### Phase 3 — 任务三：知识库增强 + OpenViking（P1+P2）

**目标**: 研报 RAG + 归因 + OV 记忆增强
**时间**: Week 4（4.09 — 4.15）

| 任务 | 说明 |
|------|------|
| 研报数据导入 | PDF 提取 + 分块 + Embedding → 向量索引 |
| RAG 检索 | FAISS 或 OV find，语义召回研报段落 |
| 多意图拆解 | LLM 自动拆解复合问题为子任务 |
| 归因分析 | 回答附带来源路径 + 原文摘要 |
| 回答格式化 | 输出含 references 的 result_3.xlsx |
| **OV Resource** | 财报 + 研报导入为 OV Resource |
| **OV Session** | 对话 commit → 记忆提取 |
| **OV 上下文增强** | 记忆召回 → 注入 prompt → 联想推荐 |

**完成标准**:
- 附件6 的 3 个示例问题能回答，含 references 归因
- OV 记忆系统可演示（多轮后能联想推荐）

### Phase 4 — 打磨 + 论文 + 自动化

**时间**: Week 5（4.16 — 4.22）

| 任务 | 说明 |
|------|------|
| 全自动 Pipeline | `pipeline.py` 一键跑完全部任务 |
| Prompt 调优 | 基于更多测试问题迭代 |
| UI 完善 | 美化、示例问题、错误提示 |
| 记忆可视化 | OV 记忆面板（如时间够） |
| 论文撰写 | 重点写 OV 创新叙事 |
| 端到端测试 | 50+ 问题覆盖 |

### Phase 5 — 提交 + 测试

**时间**: 4.23 — 4.25

| 任务 | 说明 |
|------|------|
| 4.23 | 最终检查，打包提交 |
| 4.24 | 提交截止 |
| 4.25 09:00-15:00 | 新数据测试，6 小时内出结果 |

---

## OpenViking 在系统中的角色

### 定位：任务三的增强模块 + 论文创新点

OV 不是核心依赖——没有 OV 也能完成任务一二三。
但有了 OV，系统具备了差异化的"记忆"能力。

```
不用 OV → 能完成比赛（保底）
用了 OV → 拿更高分 + 论文有故事（加分）
```

### OV 的 6 种记忆映射到财报场景

| 记忆类型 | 财报问答中的作用 | 示例 |
|----------|-----------------|------|
| profile | 用户画像 | "投资分析师，关注中药行业" |
| preferences | 关注维度 | "偏好看毛利率和研发投入" |
| entities | 关注公司 | "持续关注华润三九" |
| events | 关键查询 | "对比了多家公司的ROE" |
| cases | 成功模式 | "问营收时同时给出同比增长率效果好" |
| patterns | 回答策略 | "对比类问题 → 自动生成表格" |

### 论文核心叙事

> "传统财报问答系统是无状态的，每次提问从零开始。
> 我们引入 OpenViking 上下文数据库，赋予系统'记忆'能力——
> 记住用户的关注偏好、历史查询模式，并在后续交互中
> 主动联想相关财务指标，实现个性化、渐进式的智能问答。
> 使用时间越长，回答越贴合用户需求。"

---

## 关键参考文件索引

| 要做什么 | 去看哪里 |
|----------|----------|
| PDF 解析 | `references/FinGLM/code/finglm_all/prepare_data/pdf2txt.py` |
| 高级表格提取 | `references/FinGLM/code/南哪都队/.../excel_extraction/excel_process.py` |
| pdfplumber 用法 | `references/FinGLM/code/馒头科技/mantoutech/pdf_util.py` |
| Text2SQL 核心 | `references/chatbot_financial_statement/agent/text2sql.py` |
| Text2SQL Prompt | `references/chatbot_financial_statement/agent/prompt/` |
| DB Schema 设计 | `references/chatbot_financial_statement/ETL/dbmanager/` |
| SQL debug 重试 | `references/chatbot_financial_statement/agent/text2sql_utils.py` |
| OV 基础用法 | `references/OpenViking-examples/examples/quick_start.py` |
| OV 配置模板 | `references/OpenViking-examples/examples/ov.conf.example` |

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| PDF 表格解析质量差 | 数据不准 → 任务一不过 | 参考 FinGLM 方案，两种交易所格式分别处理 |
| 上交所 PDF 无中文文件名 | 不知道哪份是年报/季报 | 解析 PDF 内容或文件名日期推断 |
| Text2SQL 准确率低 | 任务二核心不可用 | Schema 固定只有 4 表，few-shot 覆盖常见问法 |
| 研报 RAG 召回不准 | 任务三归因错误 | 元信息过滤（行业/个股）+ Rerank |
| OV 部署/效果问题 | P2 创新点受阻 | 不影响 P0/P1，最坏退回无记忆方案 |
| 4.25 新数据处理失败 | 测试分丢失 | Pipeline 全自动化 + 提前用不同公司数据测试 |
| LLM API 不稳定 | 开发/测试受阻 | 预留备用 API |

---

## 数据概览

### 示例数据（当前已有）

- **公司**: 华润三九（深交所 000999）、金花股份（上交所 600080）
- **财报**: 2022-2025 年报/季报/半年报
- **问题**: 附件4 任务二 2 题，附件6 任务三 3 题
- **研报**: 个股研报 + 行业研报（附件5）

### 正式数据（4.11 公布）

- 预计更多中药上市公司
- 完整问题列表
- 可能有更多研报数据

### 文件命名规则

- 深交所: `A股简称：年份+报告周期+类型.pdf`（如"华润三九：2023年年度报告.pdf"）
- 上交所: `股票代码_报告日期_随机标识.pdf`（如"600080_20230428_FQ2V.pdf"）
