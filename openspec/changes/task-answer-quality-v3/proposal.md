## Why

全量测试（附件4+附件6）暴露三个答案质量短板：1) B2001 第三子问题回答 "金花股份。" 一个词完事，缺少具体数值佐证；2) Top N / 同比等数据密集型结果不自动出图，B2001 图形格式=无；3) 回答格式机械，"净利润-同比增长=271.60%" 不像自然语言。这三项直接影响评分。

## What Changes

- 增强 `build_answer_content`：同比结果行输出自然语言（"净利润同比增长 271.60%"），YoY ratio 转百分比，current/previous value 带原始字段语义
- 增强 `_select_chart_type`：Top N（多行 + stock_abbr）和同比（含 yoy_ratio 列）场景自动触发柱状图，不需要用户显式说"可视化"
- 增强 `_answer_sql`：最终拼接多子问题答案时，对 "最大/最高/最低" 类汇总子问题生成摘要句（公司名 + 具体数值），不只返回裸公司名

## Capabilities

### New Capabilities
- `auto-chart-trigger`: 基于查询结果特征（多公司排名、同比对比）自动触发图表生成，不依赖用户显式"可视化"关键词
- `yoy-answer-format`: 同比查询结果的自然语言格式化，包括百分比转换和字段语义恢复

### Modified Capabilities
- `text2sql`: `build_answer_content` 对含 `yoy_ratio`/`current_value`/`previous_value` 的结果行做语义化格式

## Impact

- `src/query/answer.py` — `build_answer_content` 新增同比结果格式化分支
- `src/knowledge/research_qa.py` — `_select_chart_type` 放宽触发条件；`_answer_sql` 增强汇总子问题的回答生成
- `src/query/chart.py` — `select_chart_type` 可能需微调（已有 `len(rows) > 1 → bar` 逻辑）
- 测试：需新增同比格式化、自动出图、汇总子问题回答的测试用例
