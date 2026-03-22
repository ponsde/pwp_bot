## Context

泰迪杯比赛项目，构建财报智能问答助手。Phase 1 是最小核心闭环：问题 → SQL → 答案。

项目当前仓库几乎为空，仅有 OpenSpec 变更文档；本 change 需要同时定义首批代码骨架、测试夹具和运行脚本。参考了三个开源项目：
- chatbot_financial_statement：两步式 Text2SQL、垂直表 Schema
- FinGLM：PDF 解析方案（pdfplumber / Camelot）
- OpenViking-examples：OV API 用法（但当前 references 目录下为 git submodule，需要以已安装 SDK 行为为准）

外部约束：
- LLM API 走 OpenAI 兼容协议（oai.whidsm.cn/v1, gpt-5.4）
- Embedding 同源（BAAI/bge-m3）
- 比赛截止 2026-04-24，Phase 1 需两周内完成

## Goals / Non-Goals

**Goals:**
- 用户能对任意 A 股上市公司的财务数据提问，获得准确数值答案
- 数据覆盖全 A 股（~5000 家），至少 3 年（2021-2023）
- Text2SQL 准确率在简单数值问题上 > 80%
- OpenViking 服务部署完成，年报全文可检索
- 最小 Gradio 界面可交互

**Non-Goals:**
- 分析型 / 语义类问题（Phase 2 RAG）
- OV 记忆系统（Session commit / 上下文增强 / 联想推荐 → Phase 2）
- 意图分类路由（Phase 2，Phase 1 全走 Text2SQL）
- 多轮对话（Phase 1 每次独立问答）
- UI 美化（Phase 3）

## Decisions

### 1. 结构化数据来源：AKShare API，不从 PDF 抠数字

**选择**：AKShare 批量拉取三张财务报表，写入 SQLite

**替代方案**：
- 从 PDF 表格中提取数字：准确率低、清洗复杂、Phase 1 时间不够
- BaoStock：字段有限（只有汇总比率），不如 AKShare 的完整三表 + 中文列名
- IEEE China-FSD 数据集：覆盖到 2022 年，缺 2023 年

**理由**：AKShare 直接给干净的 DataFrame，中文列名天然匹配用户问法（"营业收入" 对应列名就是 "营业收入"），省掉 70% ETL 工作。PDF 解析仅用于提取全文文本给 OV Resource。

**实测验证**（2026-03-22）：
- `ak.stock_financial_report_sina(stock, symbol)` 返回多报告期行 x 多指标列的 DataFrame
- `报告日` 是字符串格式如 "20231231"，需过滤年报行
- 利润表 83 列、资产负债表 147 列、现金流量表 71 列，全部中文列名
- 同时存在元数据列：`报告日`、`公告日期`、`币种`、`类型` — 需在 loader 中显式过滤，不能落入 item_name
- `ak.stock_info_a_code_name()` 只返回 code + name，无 industry 字段
- Phase 1 先做 50-100 家核心公司，全量 5000 家需要考虑 Sina API 限流

**ETL 设计要点**：
- `statement_type`：利润表 / 资产负债表 / 现金流量表（系统内部枚举，由调用参数决定）
- `report_date`：AKShare 返回的报告日（如 "20231231"）
- AKShare 的"类型"列（如"合并期末"）作为元数据列过滤掉，不进入 financial_data

### 2. SQLite Schema：垂直表设计 + 中文列名

**选择**：单表 `financial_data`，每行一个指标值（stock_code, report_date, statement_type, item_name, value）。report_date 保留 AKShare 原始格式（如 "20231231"），statement_type 使用中文（"利润表"/"资产负债表"/"现金流量表"）。companies 表 Phase 1 不含 industry 字段。

**替代方案**：
- 水平表（每列一个指标）：指标数量不固定，不同公司不同年份的项目可能不同
- 按公司类型分表（bank / non_bank）：中国 A 股不需要这么细分

**理由**：垂直表灵活度高，新增指标不需要改表结构。参考 chatbot_financial_statement 的验证结论。

**实现约束**：唯一约束 UNIQUE(stock_code, report_date, statement_type, item_name)，配合 INSERT OR IGNORE 实现幂等导入。

### 3. Text2SQL：两步式，别名映射替代向量搜索

**选择**：
- Step1: LLM 提取意图（公司/指标/年份）→ 别名映射表查 item_name
- Step2: LLM 生成 SQL（输入：用户问题 + 表结构 snapshot + Step1 映射结果）

**替代方案**：
- 一步式（直接生成 SQL）：幻觉多，没有 schema 引导容易出错
- 向量搜索匹配指标名（chatbot_financial_statement 方案）：引入 ChromaDB 依赖，Phase 1 过重

**理由**：两步式在参考项目中已验证有效。别名映射表 + SQL LIKE 足以覆盖 Phase 1 需求（"营收" → "营业收入"），Phase 2 可切换到 OV find 做语义匹配。

**实现约束**：Step1 应允许输出空列表；查询引擎需在公司未匹配、指标未匹配、年份缺失、SQL 返回空结果时给出可预期错误分支，而不是统一依赖 SQL 重试。

### 4. LLM 客户端：OpenAI SDK，同一 endpoint 同时提供 chat 和 embedding

**选择**：用 openai Python SDK，base_url 指向 oai.whidsm.cn/v1

**理由**：API 兼容 OpenAI 协议，SDK 成熟稳定。chat 用 gpt-5.4，embedding 用 BAAI/bge-m3，同一 endpoint。

### 5. OpenViking：Embedded 模式，Phase 1 只做 Resource 导入

**选择**：本地 embedded 模式（不开 HTTP server），用 `ov.OpenViking(path=...)` 或 `SyncOpenViking` 客户端

**替代方案**：HTTP server 模式：多一层网络开销，单机场景无必要

**理由**：比赛是单机环境，embedded 模式最简单。Phase 1 只验证 Resource 导入和 find 检索，不涉及 Session/Memory。注意 `add_resource(path=...)` 接受文件路径（非内存文本），可以直接传 PDF 让 OV 自行解析。

**实现校验**：`openviking==0.2.9` 的 `add_resource(path, to=None, ...)` 和 `find(query, target_uri='', limit=10, ...)` 是实际可用的 API。实现应基于"传文件路径导入"模式。

### 6. PDF 解析：pdfplumber 纯文本提取

**选择**：pdfplumber 逐页提取文本，不做表格结构化

**替代方案**：
- Camelot + pdfplumber 双保险（馒头科技方案）：Phase 1 不需要结构化表格
- 南哪都队重度后处理：过于复杂

**理由**：PDF 在 Phase 1 只用于灌入 OV Resource 做语义检索基础。全文文本提取足矣。

## Risks / Trade-offs

- **AKShare API 不稳定或被限流** → 缓解：数据拉取后本地缓存为 CSV，只拉一次；Phase 1 先做 50-100 家
- **AKShare 数据字段与用户问法不完全匹配** → 缓解：item_mapping 别名表兜底
- **AKShare 元数据列混入 item_name** → 缓解：loader 显式维护元数据列白名单，过滤 报告日/公告日期/币种/类型/数据源/更新日期
- **gpt-5.4 生成 SQL 质量不稳定** → 缓解：SQL 执行失败时自动重试（最多 2 次），错误信息反馈给 LLM
- **全 A 股数据量大，首次拉取耗时长** → 缓解：支持增量拉取、断点续传
- **OpenViking embedding 配置与 LLM endpoint 不同** → 缓解：OV 的 embedding 单独配置
- **references 目录为 submodule** → 缓解：实现阶段优先依赖已安装 SDK 行为，避免依据缺失示例误判 API
