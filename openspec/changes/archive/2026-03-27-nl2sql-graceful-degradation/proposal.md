# NL2SQL 优雅降级：部分数据也要输出

## 目标

验证/反思层判定"不满足"时，如果已有部分有效数据，应降级输出而非完全丢弃。避免用户得到空结果。

## 当前问题

### P1: "近三年"只有2年数据 → 整体失败（B2003）
- 用户问"华润三九近三年的主营业务收入情况做可视化绘图"
- SQL 查到 2023FY 和 2024FY，但 2025FY 不存在
- `_validate_result()` 或 `_reflect_task()` 判定"未满足近三年需求" → 抛 `UserFacingError`
- 正确行为：返回已有2年数据 + 附注"仅查到N年数据"

### P2: 验证失败导致图表也丢失（B2003）
- 用户明确说"做可视化绘图"，但因为验证失败，`query()` 返回 error
- pipeline 走 `elif result.error` 分支 → `chart_type_str = "none"`
- 即使有数据也不出图

### P3: 用户明确要"绘图/可视化"时 chart 判断应加权
- `select_chart_type()` 不检测"绘图"、"可视化"、"画图"等关键词
- 这些词是明确的出图意图信号

## 方案

### 改动1: `_query_with_recovery` 降级而非抛错
- 验证/反思层判定 `accepted=false` 且重试也失败时
- 如果当前 `rows` 非空，返回 `(sql, rows, intent)` + 在 rows 中附注 warning
- 引入 `QueryResult.warning` 字段，存放降级提示（如"仅查到2年数据，未满足近三年需求"）
- 只有 rows 为空时才抛 `UserFacingError`

### 改动2: `build_answer_content` 追加 warning
- `pipeline.py` 中如果 `result.warning`，在 content 末尾追加提示

### 改动3: `select_chart_type` 增加"绘图"类关键词
- 检测"绘图"、"可视化"、"画图"、"图表"→ 默认 bar（多行时）

## 范围

- `src/query/text2sql.py` — `QueryResult` 增加 warning 字段，`_query_with_recovery` 降级逻辑
- `src/query/chart.py` — `select_chart_type` 增加可视化关键词
- `pipeline.py` — warning 传递到 answer content
- `tests/` — 补测试

## 不含

- 多意图拆分（B2001 的 TOP10+同比+最大值）
- RAG 归因分析（B2003 第二轮"原因是什么"）
- validate_result.md / reflect.md prompt 调整（LLM 端行为暂不改）
