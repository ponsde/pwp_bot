## Why

task3-output-quality 端到端测试中，B2001（多意图 Top N + 同比）只得 3/10 分。核心短板：1) 同比/环比计算的 SQL 生成能力为零；2) `split_multi_intent` 拆分后子问题间的指代（"这些企业"→ top10 结果）丢失，导致后续子问题因缺公司名被拦截。这是 4.25 测试前必须解决的评分瓶颈。

## What Changes

- 新增同比/环比 SQL 生成能力：`generate_sql` 识别"同比/环比/增长率"意图，生成 self-join SQL 计算 `(本期-上期)/上期`
- 增强子问题编排：`_answer_sql` 在处理多子问题时，将前一子问题的查询结果（如公司列表）注入后续子问题的上下文，解决指代消解
- 更新 `seek_table.md` prompt：加入 `top_n`、`order_direction`、`yoy`（同比标志）字段说明和 few-shot 示例，让 LLM 路径原生支持

## Capabilities

### New Capabilities
- `yoy-calculation`: 同比/环比/增长率 SQL 生成（self-join pattern），覆盖 analyze 意图识别 + generate_sql SQL 模板
- `multi-intent-context`: 多子问题间上下文传递，前一子问题结果注入后续子问题的 conversation slot

### Modified Capabilities
- `text2sql`: seek_table.md prompt 新增 top_n/order_direction/yoy 字段 + few-shot；generate_sql 新增 self-join 模板

## Impact

- `src/query/text2sql.py` — analyze()、generate_sql()、_heuristic_intent()、_heuristic_sql() 均需修改
- `src/prompts/seek_table.md` — 新增字段说明和 few-shot 示例
- `src/knowledge/research_qa.py` — _answer_sql() 多子问题编排逻辑
- 测试：需新增同比 SQL 生成和多意图上下文传递的测试用例
