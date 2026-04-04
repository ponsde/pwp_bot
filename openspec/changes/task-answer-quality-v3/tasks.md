## 1. 同比结果自然语言格式化

- [ ] 1.1 `build_answer_content()`: 检测行中是否含 `current_value`/`previous_value`/`yoy_ratio` 三列，走 `_format_yoy_row()` 分支
- [ ] 1.2 新增 `_format_yoy_row(row, intent_fields)`: 
  - yoy_ratio 非 None → "{公司}：{年度}{指标}同比增长/下降{ratio*100:.2f}%（本期{current}，上期{previous}）"
  - yoy_ratio 为 None → "{公司}：{年度}{指标}无法计算同比（上期值为零），本期{current}"
  - `current_value`/`previous_value` 用 intent 原始字段名查 `_FIELD_UNITS` 做单位格式化
- [ ] 1.3 `build_answer_content` 签名扩展：接受可选 `intent` 参数传递原始字段名
- [ ] 1.4 调用方同步更新：`_format_sql_result` 改为 `build_answer_content(question, result.rows, intent=result.intent)`；pipeline.py `run_answer` 同理传 `result.intent`
- [ ] 1.5 测试：同比结果格式化（正增长、负增长、None 三种情况）

## 2. 自动出图

- [ ] 2.1 `ResearchQAEngine._select_chart_type()`: 移除"可视化"关键词前置检查，改为：
  - 多行 + 含 stock_abbr 列 → "bar"
  - 含 yoy_ratio 列 + 多行 → "bar"
  - 含"趋势/变化/走势" → 交给 `select_chart_type`
  - 含"可视化/绘图/画图" → 交给 `select_chart_type`
  - 其他 → "无"
- [ ] 2.2 确保任务二路径（pipeline.py `run_answer`）的图表逻辑不受影响
- [ ] 2.3 测试：Top N 查询自动出 bar；单公司查询不出图；YoY 多公司出 bar

## 3. 汇总子问题答案增强

- [ ] 3.1 `_answer_sql()`: 每个子问题回答后检测是否为汇总模式（关键词："最大/最高/最低/最多/最少/最快/最慢/第一/排名"）
- [ ] 3.2 当子问题含上述关键词且结果仅 1 行时，用 `build_answer_content` 格式化该行，前缀为"排名第一的是"或对应表述
- [ ] 3.3 测试："最大增幅是哪家" 子问题回答包含公司名 + 具体数值

## 4. 回归验证

- [ ] 4.1 现有 pytest 不退化
- [ ] 4.2 B2001 端到端重新测试，验证三个改进点
