## 1. 图表 label 格式化

- [x] 1.1 `chart.py` `pick_chart_columns`：返回 `label_field` 名称（当前只返回 label 值），或在 `safe_chart_data` 中记录 `label_field` 名
- [x] 1.2 `chart.py` `safe_chart_data`：当 `label_field == "report_period"` 时，对 label 调用 `_format_report_period`（从 `answer.py` 导入）
- [x] 1.3 测试：图表 data 中 `2022FY` label 转为 `2022年`

## 2. 图表数据标注带单位

- [x] 2.1 `chart.py` `render_chart`：折线图标注从 `f"{v:,.2f}"` 改为 `f"{v:,.2f}{unit_label}"`
- [x] 2.2 `chart.py` `render_chart`：柱状图标注同上
- [x] 2.3 饼图标注不变（已用百分比）
- [x] 2.4 测试：确认标注含单位后缀

## 3. 多子问题答案去重

- [x] 3.1 `research_qa.py` `_answer_sql`：在 `"\n".join(answer_parts)` 后做行级去重（保持首次出现顺序）
- [x] 3.2 测试：两个子问题返回重叠数据时，最终答案无重复行

## 4. YoY 回退答案语义

- [x] 4.1 `text2sql.py` `_query_with_recovery`：YoY 回退分支在返回前给 `current_intent` 设置 `"yoy_fallback": True`
- [x] 4.2 `answer.py` `build_answer_content`：当 `intent.get("yoy_fallback")` 为真且行不含同比结构时，在答案末尾追加 `（无法计算同比，仅显示本期值）`
- [x] 4.3 测试：YoY 回退场景答案包含"无法计算同比"

## 5. 回归验证

- [x] 5.1 现有 pytest 不退化
- [ ] 5.2 附件4 + 附件6 全量测试，确认图表 label、答案去重、YoY 回退均改善
