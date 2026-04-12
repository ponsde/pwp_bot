## Context

当前 `build_answer_content` 以 "字段名=值" 格式逐行拼接，所有字段一视同仁。同比结果的列名是 `current_value`/`previous_value`/`yoy_ratio`（由 `_build_yoy_sql` 生成），不在 `_FIELD_LABELS`/`_FIELD_UNITS` 映射中，直接输出英文别名。

图表触发逻辑 `_select_chart_type` 必须问题含"可视化/绘图/图表/画图"关键词才出图。B2001 问 Top 10 排名但没说"可视化"，所以图形=无。

`_answer_sql` 多子问题答案直接 join，无汇总逻辑。"最大增幅是哪家" 子问题若 LLM 只返回一个公司名（SQL `LIMIT 1`），`build_answer_content` 输出一行数据，缺乏完整上下文。

## Goals / Non-Goals

**Goals:**
- 同比结果行用自然语言表述："{公司} {年度} {指标}同比增长 {ratio}%（本期 {current}，上期 {previous}）"
- Top N（多行含 stock_abbr）和同比（含 yoy_ratio）场景自动触发柱状图
- "最大/最高/最低" 汇总子问题回答包含完整数据（公司名 + 指标值 + 增幅）

**Non-Goals:**
- 不重构 `_build_yoy_sql` 的列名（current_value/previous_value/yoy_ratio 保持不变）
- 不改 pipeline.py 的输出格式
- 不做任务二（附件4）的答案优化

## Decisions

### 1. 同比格式化：在 `build_answer_content` 中检测 yoy_ratio 列

**选择**：在 `build_answer_content` 中，当 row 同时包含 `current_value`/`previous_value`/`yoy_ratio` 时，走专门的同比格式化分支。根据 intent 中的原始 fields 名恢复字段语义（通过 `_FIELD_LABELS` 查找）。

**替代方案**：在 `_build_yoy_sql` 中改用原始字段名别名 —— 但会改变 SQL 输出格式，影响面更大。

### 2. 自动出图：放宽 `_select_chart_type` 触发条件

**选择**：在 `ResearchQAEngine._select_chart_type` 中，除了检查"可视化"关键词，还检查结果特征：
- 多行 + stock_abbr 列存在 → bar
- 含 yoy_ratio 列 → bar

不修改 `chart.py` 的 `select_chart_type`（它已有 `len(rows) > 1 → bar` 逻辑），只改 research_qa 层的入口过滤。

**理由**：任务二的图表逻辑由用户显式触发是合理的；任务三面对研报复合问题，应更积极出图。

### 3. 汇总子问题增强：在 `_answer_sql` 中检测 "最大/最高/最低" 模式

**选择**：当子问题包含"最大/最高/最低/最多/最少"且结果只有 1 行时，回答追加完整数据行而非只返回公司名。用 `build_answer_content` 格式化该行，前缀加"排名第一的是"。

## Risks / Trade-offs

- [自动出图可能误触发] 某些多行结果不适合柱状图（如多个报告期的趋势）→ 缓解：只在有 stock_abbr 列时触发 bar，趋势走 line
- [同比格式化依赖列名约定] 如果 LLM 路径生成的 SQL 不用 current_value/previous_value/yoy_ratio 别名，格式化不生效 → 可接受，LLM 路径结果本身有原始字段名，走默认格式化
