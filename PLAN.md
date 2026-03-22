# 财报"智能问数"助手 — 项目计划

## 项目信息

- **比赛**: 泰迪杯
- **截止**: 2026-04-24
- **起始**: 2026-03-22
- **可用时间**: ~33 天（实际投入约 50%）
- **LLM API**: gpt-5.4 via oai.whidsm.cn
- **Embedding**: BAAI/bge-m3 via siliconflow
- **创新点**: OpenViking 上下文记忆系统

---

## 架构设计

### 三引擎架构：各司其职

```
┌──────────────────────────────────────────────────────────────┐
│                       Gradio UI                               │
│  对话界面 │ 数据溯源面板 │ 记忆可视化面板 │ 检索轨迹面板       │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                      Orchestrator                             │
│                                                               │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ OV 上下文 │──▶│ 意图识别  │──▶│ 查询路由  │──▶│ 回答生成  │  │
│  │ 增强     │   │ + 分类   │   │          │   │ + 联想   │  │
│  └──────────┘   └──────────┘   └────┬─────┘   └──────────┘  │
│                                     │                         │
└─────────────────────────────────────┼─────────────────────────┘
              ┌───────────────────────┼───────────────┐
              ▼                       ▼               ▼
  ┌─────────────────┐   ┌──────────────────┐   ┌──────────────────────┐
  │  精确查询引擎     │   │  语义检索引擎     │   │  上下文记忆引擎       │
  │  (Text2SQL)      │   │  (RAG)           │   │  (OpenViking) ★      │
  │                  │   │                  │   │                      │
  │  自然语言 → SQL  │   │  Embed → 召回    │   │  ┌────────────────┐  │
  │  SQL → 执行结果  │   │  Rerank → 精排   │   │  │ Resource       │  │
  │                  │   │                  │   │  │ 财报原文/行业   │  │
  │  SQLite          │   │  FAISS / OV find │   │  └────────────────┘  │
  └─────────────────┘   └──────────────────┘   │  ┌────────────────┐  │
                                                │  │ Memory         │  │
                                                │  │ 用户画像       │  │
                                                │  │ 偏好/关注实体  │  │
                                                │  │ 查询案例/模式  │  │
                                                │  └────────────────┘  │
                                                │  ┌────────────────┐  │
                                                │  │ Session        │  │
                                                │  │ 对话 → commit  │  │
                                                │  │ → 记忆提取     │  │
                                                │  │ → 自迭代       │  │
                                                │  └────────────────┘  │
                                                └──────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                       ETL 数据处理层                           │
│  PDF (pdfplumber) → 表格提取 → 清洗 → SQLite 入库             │
│                   → 文本分块 → Embedding → 向量索引            │
│                   → 全文导入 → OpenViking Resource             │
└──────────────────────────────────────────────────────────────┘
```

### 三引擎的定位

| 引擎 | 解决什么问题 | 什么时候用 |
|------|-------------|-----------|
| **Text2SQL** | "茅台2023年营收多少？" → 精确数值 | 数值型问题（核心） |
| **RAG** | "公司的发展战略是什么？" → 文本段落 | 分析型/描述型问题 |
| **OpenViking** | 记住用户关注什么 → 联想推荐 | 贯穿全程（创新点） |

### OpenViking 在系统中的角色（创新点）

OpenViking **不是**做精确查询或传统 RAG 的，它的价值在于赋予系统"记忆"：

```
用户第一次问："华为2023年营收多少？"
  → Text2SQL 回答：7042亿元
  → OV 记录：用户关注华为、关注营收      ← Session commit

用户第二次问："那研发投入呢？"
  → OV 上下文增强：用户在聊华为           ← Memory 召回
  → Text2SQL 回答：1647亿元
  → OV 联想："研发占营收 23.4%，行业领先" ← Resource + Pattern

用户第三次问："跟同行比呢？"
  → OV 知道用户关注科技行业 + 营收/研发    ← Profile + Preference
  → 主动拉出中兴、小米等同行数据对比       ← 联想推荐
```

**OpenViking 的 6 种记忆映射到财报场景：**

| 记忆类型 | 财报问答中的作用 | 示例 |
|----------|-----------------|------|
| profile | 用户画像 | "投资分析师，关注科技行业" |
| preferences | 关注维度 | "偏好看毛利率和研发投入" |
| entities | 关注公司 | "持续关注华为、腾讯、比亚迪" |
| events | 关键查询 | "3月10日对比了三家公司的ROE" |
| cases | 成功模式 | "问营收时，同时给出同比增长率效果好" |
| patterns | 回答策略 | "对比类问题 → 自动生成表格" |

### 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 结构化DB | SQLite | 轻量、零配置、比赛够用 |
| 表设计 | 垂直表为主 | 参考 chatbot_financial_statement，灵活度高 |
| Text2SQL | 两步式 | Step1 选表选列 → Step2 生成 SQL，减少幻觉 |
| RAG 向量检索 | FAISS 或 OV find | Phase 2 再定，哪个顺手用哪个 |
| 记忆/联想 | OpenViking Session + Memory | 创新点，差异化核心 |
| UI | Gradio | 快速出界面，评审友好 |
| PDF 解析 | pdfplumber | 参考 FinGLM 馒头科技/finglm_all 方案 |

---

## 项目结构

```
taidi_bei/
├── PLAN.md                    ← 本文件
├── AI-CONTEXT.md              ← Agent 共享项目背景（后续生成）
│
├── src/                       ← 源代码
│   ├── __init__.py
│   │
│   ├── etl/                   ← 数据处理层
│   │   ├── __init__.py
│   │   ├── pdf_parser.py      ← PDF 解析（pdfplumber）
│   │   ├── table_extractor.py ← 表格提取与清洗
│   │   ├── schema.py          ← SQLite 表结构定义
│   │   └── loader.py          ← 数据入库（SQLite + OpenViking Resource）
│   │
│   ├── query/                 ← 查询引擎层
│   │   ├── __init__.py
│   │   ├── intent.py          ← 意图分类（数值型/分析型）
│   │   ├── text2sql.py        ← 两步式 Text2SQL 核心
│   │   ├── retriever.py       ← 语义检索（FAISS 或 OV find）
│   │   └── fusion.py          ← 结果融合与回答生成
│   │
│   ├── llm/                   ← LLM 接入层
│   │   ├── __init__.py
│   │   └── client.py          ← LLM API 封装
│   │
│   ├── viking/                ← OpenViking 集成层 ★
│   │   ├── __init__.py
│   │   ├── client.py          ← OV 客户端封装（初始化/连接）
│   │   ├── resource.py        ← Resource 管理（财报导入/检索）
│   │   ├── session.py         ← Session 管理（对话 → commit → 记忆提取）
│   │   └── context.py         ← 上下文增强（记忆召回 → 联想推荐）
│   │
│   └── prompts/               ← Prompt 模板
│       ├── seek_database.md   ← Step1: 选表选列
│       ├── generate_sql.md    ← Step2: 生成 SQL
│       ├── answer.md          ← 回答生成（含联想推荐）
│       └── intent.md          ← 意图分类
│
├── app.py                     ← Gradio 入口
├── config.py                  ← 配置管理（API keys 从环境变量读取）
├── ov.conf                    ← OpenViking 配置
│
├── data/                      ← 数据目录
│   ├── raw/                   ← 原始 PDF 年报
│   ├── db/                    ← SQLite 数据库文件
│   └── processed/             ← 中间处理结果
│
├── tests/                     ← 测试
│   ├── test_pdf_parser.py
│   ├── test_text2sql.py
│   ├── test_viking.py         ← OV 集成测试
│   └── test_queries.py        ← 端到端问答测试用例
│
├── evaluate/                  ← 评估
│   └── benchmark.py           ← 问答准确率评测
│
├── references/                ← 参考项目（已 clone）
│   ├── chatbot_financial_statement/
│   ├── FinGLM/
│   └── OpenViking-examples/
│
├── docs/                      ← 论文和文档
│   └── paper/                 ← 泰迪杯论文
│
└── requirements.txt
```

### 结构设计说明

- `viking/` 独立模块，是项目的创新点所在，包含 OV 的所有集成逻辑
- `query/retriever.py` 做通用语义检索，底层可以切换 FAISS 或 OV find
- `prompts/` 独立存放，回答模板包含联想推荐的指令
- 每个模块职责单一，文件 < 400 行

---

## 分阶段计划

### Phase 1 — 能答题（核心闭环）

**目标**: PDF → SQLite → 问题 → SQL → 答案，同时搭好 OpenViking
**时间**: Week 1-2（3.22 — 4.04）

| 任务 | 关键参考 | 产出 |
|------|----------|------|
| 环境搭建 | — | Python 环境、依赖安装 |
| OpenViking 部署 | OV examples/ov.conf | `ov.conf` + OV 服务跑通 |
| PDF 解析 | FinGLM 馒头科技 pdf_util.py | `etl/pdf_parser.py` |
| 表格提取与清洗 | FinGLM 南哪都队 excel_process.py | `etl/table_extractor.py` |
| SQLite Schema 设计 | chatbot_financial_statement ETL/ | `etl/schema.py` |
| 数据入库（SQLite） | — | `etl/loader.py` |
| 财报导入 OV Resource | OV examples quick_start.py | `viking/resource.py` |
| LLM 接入 | — | `llm/client.py` |
| 两步式 Text2SQL | chatbot_financial_statement agent/ | `query/text2sql.py` |
| Prompt 模板 v1 | chatbot_financial_statement Prompts/ | `prompts/*.md` |
| 基础 Gradio 界面 | — | `app.py` |

**Phase 1 完成标准**:
- 能对至少一份年报提问"XX公司2023年营业收入是多少？"并得到正确答案
- OpenViking 服务正常运行，财报已导入为 Resource

### Phase 2 — 答得好 + OV 记忆上线（质量 + 创新）

**目标**: 提高准确率，OpenViking 记忆系统投入使用
**时间**: Week 3（4.05 — 4.11）

| 任务 | 说明 |
|------|------|
| 意图分类 | 区分数值型 vs 分析型，路由到不同引擎 |
| 语义检索接入 | 分析型问题走 OV find / FAISS |
| OV Session 集成 | 对话自动 commit → 记忆提取 |
| OV 上下文增强 | 回答前召回用户记忆，注入 prompt |
| 结果融合 | Text2SQL 结果 + 检索结果 + 记忆上下文 → 合并回答 |
| SQL 失败重试 | 错误信息反馈 LLM 重新生成（最多 2 次） |
| Prompt 调优 | 基于测试用例迭代 |
| 多份年报支持 | 扩展到赛题要求的数据量 |

**Phase 2 完成标准**:
- 数值型问题准确率 > 70%
- 多轮对话中系统能记住用户关注的公司和指标
- 能做出基本的联想推荐

### Phase 3 — 打磨亮点（差异化 + 论文）

**目标**: 完善 OV 记忆体验，做好可视化，撰写论文
**时间**: Week 4（4.12 — 4.18）

| 任务 | 说明 |
|------|------|
| 联想推荐完善 | 基于 cases/patterns 主动推荐相关指标、同行对比 |
| 记忆可视化面板 | Gradio 中展示 OV 提取的用户画像、关注实体 |
| 检索轨迹面板 | 展示回答来源（哪页、哪个表、哪段原文） |
| 数据溯源 | 回答附带来源引用 |
| UI 完善 | 美化界面、添加示例问题、错误提示 |
| 论文撰写 | 重点写 OV 记忆系统的创新叙事 |

**论文核心叙事**:
> "传统财报问答系统是无状态的，每次提问从零开始。
> 我们引入 OpenViking 上下文数据库，赋予系统'记忆'能力——
> 记住用户的关注偏好、历史查询模式，并在后续交互中
> 主动联想相关财务指标，实现个性化、渐进式的智能问答。
> 使用时间越长，回答越贴合用户需求。"

### Phase 4 — 收尾提交

**时间**: Week 5（4.19 — 4.24）

| 任务 | 说明 |
|------|------|
| 端到端测试 | 完整流程测试、边界情况 |
| 论文定稿 | 图表、实验数据、参考文献 |
| 打包提交 | 按比赛要求整理 |

---

## OpenViking 集成详解

### 数据流：OpenViking 如何贯穿全流程

```
┌─ ETL 阶段 ─────────────────────────────────────────────────┐
│                                                              │
│  财报 PDF → pdfplumber 解析                                   │
│    ├─ 结构化表格 → SQLite（精确查询用）                         │
│    └─ 全文文本   → OV add_resource（语义检索 + 记忆关联用）     │
│                                                              │
└──────────────────────────────────────────────────────────────┘

┌─ 查询阶段 ─────────────────────────────────────────────────┐
│                                                              │
│  用户提问                                                     │
│    │                                                         │
│    ├─ 1. OV 上下文增强                                        │
│    │   → session 召回历史记忆                                  │
│    │   → 用户画像：关注什么行业/公司/指标                       │
│    │   → 历史 cases：类似问题曾怎么回答                         │
│    │   → 注入 prompt："用户是XX角色，关注YY，上次问了ZZ"        │
│    │                                                         │
│    ├─ 2. 意图分类（被 OV 上下文增强后更准）                     │
│    │   → 数值型 → Text2SQL                                    │
│    │   → 分析型 → RAG (OV find / FAISS)                       │
│    │                                                         │
│    ├─ 3. 执行查询，获得结果                                    │
│    │                                                         │
│    ├─ 4. 回答生成 + OV 联想                                    │
│    │   → 基础回答（查询结果）                                  │
│    │   → 联想推荐（基于 entities/preferences 关联更多信息）     │
│    │   → "您之前关注过研发投入，补充：研发占营收 23.4%"         │
│    │                                                         │
│    └─ 5. OV Session commit                                    │
│        → 记录本次对话                                         │
│        → 提取记忆：用户关注了什么新公司/指标                    │
│        → 沉淀模式：什么类型的回答用户满意                       │
│        → 自迭代：去重、合并、更新已有记忆                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### OV API 使用模式

```python
# 初始化
client = ov.OpenViking(path="./data/ov")
client.initialize()

# ETL: 导入财报为 Resource
result = client.add_resource(
    path="data/raw/华为2023年报.pdf",
    reason="华为2023年度报告全文"
)
client.wait_processed()  # 等待 L0/L1/L2 索引生成

# 查询前: 上下文增强
session = client.session()
# 从历史 session 加载记忆
results = client.search(
    "用户关注的公司和指标",
    session_id=session.session_id,
    limit=5
)

# 语义检索 (替代或补充 FAISS)
results = client.find("华为发展战略", limit=3)

# 查询后: 记录对话并提取记忆
session.add_message(role="user", content="华为2023年营收多少？")
session.add_message(role="assistant", content="7042亿元...")
client.commit_session(session.session_id)  # 自动提取记忆
```

---

## Text2SQL 两步策略详解

参考 chatbot_financial_statement 的核心设计：

```
用户问题: "贵州茅台2023年营业收入是多少？"

Step 1 — 选表选列 (seek_database)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  输入: 用户问题 + OV 上下文（用户关注偏好）
  LLM 输出:
    {
      "companies": ["贵州茅台"],
      "accounts": ["营业收入"],
      "years": [2023]
    }
  系统动作:
    → 查找公司对应的 stock_code
    → 查找"营业收入"对应的 category_code
    → 取出相关表的 snapshot（列名 + 示例数据）

Step 2 — 生成 SQL (reasoning_text2sql)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  输入: 用户问题 + Step1 的表 snapshot + OV 记忆上下文
  LLM 输出:
    SELECT data FROM financial_statement
    WHERE stock_code = '600519'
      AND category_code = 'IS_001'
      AND year = 2023;

Step 3 — 执行 & 回答 + 联想
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  执行 SQL → 拿到结果 → LLM 生成回答
  如果 SQL 报错 → 反馈 LLM 重试（最多 2 次）
  OV 联想 → 基于用户画像补充相关信息
```

---

## SQLite Schema 设计（草案）

采用**垂直表设计**（参考 chatbot_financial_statement）：

```sql
-- 公司基本信息
CREATE TABLE companies (
    stock_code TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    industry TEXT,
    exchange TEXT
);

-- 财务数据（垂直表：每行一个指标）
CREATE TABLE financial_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    year INTEGER NOT NULL,
    report_type TEXT NOT NULL,      -- 'annual' / 'quarterly'
    statement_type TEXT NOT NULL,   -- 'balance_sheet' / 'income' / 'cash_flow'
    item_name TEXT NOT NULL,        -- 中文指标名（如"营业收入"）
    item_code TEXT,                 -- 标准化代码（如 IS_001）
    value REAL,
    unit TEXT DEFAULT '元',
    FOREIGN KEY (stock_code) REFERENCES companies(stock_code)
);

-- 指标映射表（中文名 → 标准代码，含别名）
CREATE TABLE item_mapping (
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,        -- 可能的中文名称（含别名）
    statement_type TEXT NOT NULL,
    is_primary INTEGER DEFAULT 0,   -- 1 = 主名称
    PRIMARY KEY (item_code, item_name)
);
```

垂直表的优势：年报里指标数量不固定，不同公司、不同年份的报表项目可能不同。
垂直表天然适应这种变化，不需要改表结构。

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
| OV Session/Memory | `references/OpenViking-examples/examples/` |

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| PDF 表格解析质量差 | 数据不准 → SQL 结果错 | 先用 FinGLM 验证过的方案，复杂表格用 Camelot 兜底 |
| Text2SQL 准确率低 | 核心功能不可用 | 准备 20+ few-shot 示例，覆盖常见问法 |
| OpenViking 部署困难 | 记忆功能受阻 | Phase 1 核心不依赖 OV 记忆，但 OV 部署并行推进 |
| OV 记忆提取效果差 | 联想不准确 | 调优 commit 的 prompt，手动验证记忆质量 |
| LLM API 不稳定 | 开发受阻 | 预留备用 API（siliconflow 等） |
| 时间不够 | 功能不完整 | Phase 1 是最小可交付，OV 记忆是 Phase 2 的增量 |
