# NL2SQL 回答质量优化

## 目标

修复实测发现的 3 个效果问题，提升回答质量和图表准确性。

## 当前问题

### P1: 比较类回答缺公司名（T004）
- `build_answer_content()` 对多行结果过滤掉了 `stock_abbr` 列
- 导致"金花股份和华润三九2023年营业收入对比"回答变成两行数字，看不出谁是谁
- 期望：`金花股份：5.65亿元，华润三九：247.39亿元`

### P1: 单值查询被误判为折线图（T001）
- `select_chart_type()` 只看问题文本中的关键词（"趋势"、"季度"等）
- 多轮对话中第二轮 "2025年第三季度的" 包含"季度"，被判为折线图
- 但实际结果只有 1 行数据，画折线图无意义
- 期望：结果 ≤1 行时强制返回 `none`

### P2: 计算类问题不支持（T010）
- 问"净利润占营业收入的比例"，LLM 去查 `net_profit_margin` 字段（不存在）
- 三层恢复也救不回来，因为根本没有这个字段
- 需要教 LLM 生成 `SELECT net_profit * 1.0 / total_operating_revenue` 这类计算 SQL
- 同时需要在 generate_sql.md prompt 中加入计算类 few-shot 示例

## 范围

- `src/query/answer.py` — 多行回答保留公司名标识
- `src/query/chart.py` — 结果行数 ≤1 时不出图
- `src/prompts/generate_sql.md` — 增加计算类 SQL few-shot
- `src/prompts/seek_table.md` — 增加计算类意图解析示例（跨字段计算需要两个字段）

## 不含

- LLM 驱动的自然语言回答生成（`answer.md` 模板）
- 图表样式美化
- 新增数据库字段
