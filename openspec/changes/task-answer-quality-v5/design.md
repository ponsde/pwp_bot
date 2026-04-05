## Context

v4 修复了文本答案中的 `report_period` 格式化，但图表的 label 取自 `safe_chart_data` → `pick_chart_columns`，直接用 `str(row["report_period"])` 输出原始值（如 `2022FY`）。`render_chart` 的数据标注用 `f"{v:,.2f}"` 不带单位，而 Y 轴已有 `unit_label`。

`_answer_sql` 多子问题拼接时，去重用 `(sql, rows_json)` 签名，但如果两个子问题返回不同 SQL 却含有部分重叠内容（如第一个问 top10 利润、第二个问这些公司的同比），`answer_parts` 直接拼接会出现同一公司的利润数据重复出现。

YoY 回退（`_query_with_recovery:188-197`）在上年同期缺失时返回 `_build_single_period_sql` 的原始行（只有普通字段），后续 `build_answer_content` 会把它格式化为普通数值，主答案不含"无法计算同比"的语义。

## Goals / Non-Goals

**Goals:**
- 图表 X 轴 `report_period` 显示为人类可读格式（2022年、2024年第三季度）
- 图表折线图/柱状图数据标注带单位后缀（如 `4,790.10万元`）
- 多子问题拼接后消除答案段落级重复
- YoY 回退场景主答案包含"无法计算同比"语义

**Non-Goals:**
- 不重构 `_answer_sql` 的去重逻辑（仅在输出层去重）
- 不改 `_build_single_period_sql` 的 SQL 生成逻辑
- 不改图表颜色、尺寸等样式

## Decisions

### 1. 图表 label 格式化：在 `safe_chart_data` 中处理

**选择**：在 `safe_chart_data` 中，当 `label_field == "report_period"` 时，对 label 值调用 `_format_report_period`（从 `answer.py` 导入）。

**替代方案**：在 `render_chart` 中对 labels 做后处理 → 但 `render_chart` 不知道 label 的语义，`safe_chart_data` 是知道 field 名的最后一个环节。

### 2. 数据标注带单位：在 `render_chart` 中拼接

**选择**：`render_chart` 中标注格式从 `f"{v:,.2f}"` 改为 `f"{v:,.2f}{unit_label}"`（`unit_label` 已由 `_detect_unit_scale` 计算）。饼图不受影响（已用百分比）。

### 3. 答案去重：在 `_answer_sql` 拼接后做行级去重

**选择**：在 `_answer_sql` 的 `"\n".join(answer_parts)` 之后，按行 split 并去除重复行（保持首次出现顺序）。

**替代方案**：在 `_format_sql_result` 层去重 → 但重复是跨子问题产生的，单个子问题内部不重复。

**理由**：行级去重简单有效，不改变底层查询逻辑，风险最低。

### 4. YoY 回退答案语义：在 `build_answer_content` 增加 fallback 分支

**选择**：在 `_query_with_recovery` 的 YoY 回退分支中，将返回的 `current_intent` 标记 `yoy_fallback: True`。在 `build_answer_content` 中，当 `intent.get("yoy_fallback")` 为真时，对普通行追加"（无法计算同比，仅显示本期值）"后缀。

**替代方案**：在 `_query_with_recovery` 中构造伪 YoY 行（`yoy_ratio=None`）→ 但会引入虚假数据结构，风险较高。

## Risks / Trade-offs

- [行级去重可能误删合法重复行] → 缓解：只对完全相同的行去重，不同上下文中相同数值的行概率很低
- [图表标注带单位可能过长] → 缓解：`_detect_unit_scale` 已做了合理缩放，标签不会太长
