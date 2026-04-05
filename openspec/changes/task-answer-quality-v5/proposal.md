## Why

全量测试（附件4 + 附件6）暴露三类答案质量问题：1) 图表 X 轴仍显示原始 `2022FY` 而非 `2022年`，且数据标注无单位后缀；2) 任务三多子问题拼接后答案出现重复段落（B2001 金花股份利润重复两次、B2003 华润三九营收重复两遍）；3) YoY 回退场景主答案退化为普通数值而非"无法计算同比"。

## What Changes

- 图表 `safe_chart_data` / `pick_chart_columns` 中 label 为 `report_period` 时调用 `_format_report_period` 转换
- 图表数据标注增加单位后缀（与 Y 轴单位一致）
- `_answer_sql` 多子问题拼接后对 `answer_parts` 做段落级去重，消除重复行
- YoY 回退分支（上年同期缺失时）主答案增加"无法计算同比"语义，而非只输出普通本期值

## Capabilities

### New Capabilities
- `chart-label-formatting`: 图表 label 格式化（report_period 可读化 + 数据标注带单位）

### Modified Capabilities
- `answer-formatter`: 多子问题拼接去重；YoY 回退场景答案语义
- `text2sql`: YoY 回退分支返回结果的语义保证

## Impact

- `src/query/chart.py` — `pick_chart_columns` / `safe_chart_data` label 格式化，`render_chart` 数据标注
- `src/knowledge/research_qa.py` — `_answer_sql` 拼接去重
- `src/query/text2sql.py` — `_query_with_recovery` YoY 回退分支
- `src/query/answer.py` — 可能需要新增 YoY 回退格式化函数
- 测试：需新增图表 label、去重、YoY 回退的测试用例
