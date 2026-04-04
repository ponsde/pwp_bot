## Context

泰迪杯 B 题，中药上市公司财报"智能问数"助手。示例数据：华润三九（深交所 000999）、金花股份（上交所 600080），39 份财报 PDF，2022-2025 年报/季报/半年报。

赛题三个任务：任务一 PDF→DB、任务二 NL2SQL、任务三 RAG。Phase 1 覆盖任务一全部 + 任务二核心。

关键约束：
- Schema 由官方指定（附件3），4 张表，字段固定
- report_period 格式："2025Q3"/"2022FY"/"2024HY"/"2023Q1"
- 4.25 测试给新数据，6 小时内 Pipeline 跑完出结果
- 输出必须按附件7 JSON 格式 + xlsx

**参考项目**（实现时必须参考，不要蒙头做）：
- `references/FinGLM/code/南哪都队/.../excel_extraction/excel_process.py` — 95+ 财务术语别名映射、行名标准化、模板验证
- `references/FinGLM/code/馒头科技/mantoutech/financial_state.py` — 多层表格定位策略（关键词+确认词+无效词过滤）
- `references/FinGLM/code/馒头科技/mantoutech/file.py` — get_unit() 单位检测（当前页+上一页搜索）
- `references/FinGLM/code/finglm_all/prepare_data/cut_table_fin.py` — 正则表格起止检测
- `references/chatbot_financial_statement/agent/text2sql.py` — 两步式 Text2SQL + 3 层错误恢复

## Goals / Non-Goals

**Goals:**
- 华润三九 + 金花股份全部 PDF 自动解析入库，4 张表数据完整
- 关键字段覆盖率 > 80%（营收、净利润、利润总额、总资产等核心字段不能 None）
- 附件4 的 2 个示例问题能正确回答
- `python pipeline.py --task etl` 一键入库
- 输出符合附件7 格式的 result_2.xlsx + 图表图片

**Non-Goals:**
- 研报 RAG / 归因分析（Phase 3，任务三）
- OpenViking 记忆系统（Phase 3，P2 创新点）
- 多意图拆解（Phase 3）
- UI 美化（Phase 4）

## Decisions

### 1. PDF 表格定位：多层策略（参考馒头科技 + 南哪都队）

**选择**：三层定位策略，不是简单的页面文本关键词匹配

```
第一层：标题关键词定位
  required_keywords: ["合并资产负债表", "合并利润表", "合并现金流量表"]
  invalid_keywords: ["母公司资产负债表", "母公司利润表"]

第二层：确认关键词验证（表格内容必须包含期望字段）
  合并资产负债表 → 确认词: "货币资金"
  合并利润表 → 确认词: "营业收入" 或 "营业总收入"
  合并现金流量表 → 确认词: "销售商品" 或 "经营活动"

第三层：表格自身内容分类（非页面文本）
  用表格前 3 行的实际单元格内容判断类型
  同一页多个表可以被正确区分
```

**参考**：馒头科技的 `find_match_page()` 用 required_line_keywords + required_post_keywords 双重验证。

### 2. 别名字典：大规模覆盖（参考南哪都队 95+ 别名）

**选择**：维护完整的中文→英文字段映射字典，覆盖各种变体

**标准化流程**（参考南哪都队 excel_process.py）：
```
PDF 原文行名
  → rm_prefix(): 去序号前缀（"一、" "二、" "（一）" "1."）
  → 去括号注释（"（亏损以"－"号填列）"）
  → 别名匹配（95+ 别名组）
  → 官方英文字段名
```

**关键别名组（必须覆盖）**：
- "营业收入" / "一、营业总收入" / "营业总收入" → total_operating_revenue
- "净利润" / "四、净利润" / "五、净利润" / "归属于母公司所有者的净利润" → net_profit
- "利润总额" / "三、利润总额" / "四、利润总额" → total_profit
- "资产合计" / "总资产" / "资产总额" / "资产总计" → asset_total_assets
- "负债合计" / "总负债" → liability_total_liabilities
- ... 详见 excel_process.py 的 features_alias

### 3. 单位检测：搜索范围扩大（参考馒头科技 get_unit()）

**选择**：在表格标题行、当前页文本、上一页末尾搜索"单位：X元"

**参考**：馒头科技 file.py 的 `get_unit()` 搜索当前页 + 前一页最后 10 行，支持元/万元/千元/百万元四级。

### 4. 跨页表格合并：带模板验证

**选择**：
- 同类型 + 相邻页 → 合并
- 未分类表 + 紧邻已分类表 → 继承类型并合并
- **同一页不同表 → 不合并**（修复了之前的致命 bug）
- 合并后去重（参考南哪都队的重复行检测）

### 5. NL2SQL：完整 Schema + few-shot 示例

**选择**：4 张表的完整 CREATE TABLE 放进 prompt + 手工 few-shot 示例

**参考**：chatbot_financial_statement 用向量搜索找相似 SQL 作为 few-shot。Phase 1 先手工准备 20-30 个 few-shot 覆盖常见问法，Phase 2 考虑向量化。

**3 层错误恢复**（参考 chatbot_financial_statement）：
1. 自动 debug：SQL 报错 → 错误信息反馈 LLM 重试（最多 3 次）
2. 自动修正：执行成功但结果不合理 → LLM 判断是否正确
3. 自动反思：结果不满足原始任务 → 重新理解任务并重试

Phase 1 先实现第 1 层，后续加 2-3 层。

### 6. report_period 统一格式

`report_period` 使用完整格式 `{year}{period}`（如 2023FY、2024Q1），report_year 存独立整数列。SQL 生成时统一用完整格式。

### 7. 多轮对话：上下文槽位继承

维护会话槽位（company/field/period），追问时从上轮补全缺失槽位。

### 8. 图表生成：规则优先

折线图（趋势）、柱状图（对比）、饼图（占比），规则式选择。

## Risks / Trade-offs

- **PDF 表格格式多变** → 缓解：参考 FinGLM 多队方案，别名字典覆盖 95+ 变体
- **同页多表误判** → 缓解：表格自身内容分类 + 确认关键词验证
- **单位不一致** → 缓解：字段级单位元数据 + 扩大搜索范围检测源单位
- **4.25 新数据** → 缓解：Pipeline 全自动 + per-file 错误隔离 + 未知公司优雅降级
