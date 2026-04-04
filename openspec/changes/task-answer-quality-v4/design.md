## Context

`text2sql.py` 的三层恢复机制（SQL重试 → 结果验证 → 反思重分析）会产生 `warning` 字段，通过 `QueryResult.warning` 传递。`pipeline.py` 的 `run_answer` 会将 warning 追加到用户答案尾部：`content += f"\n（注：{result.warning}）"`。当 LLM 验证/反思层生成冗长的��部分析文本时（如"原始问题本身是一个待补充/澄清的提问模板..."），这些内部 reasoning 会直接暴露给用户。

`_answer_sql` 多子问题拼接时，每个子问题调用 `_format_sql_result(sub_question, result)`，其中 `build_answer_content(question, rows)` 对单行单列结果输出 `f"{question}：{value}"`。当子问题文本很长（如"在这些企业中，利润或销��额年同比上涨幅度最大的是哪家企业"），整段���问题文本会出现在答案中，显得不自然。

多���格式化中 identifiers 直接输出 `report_period` 原始值（如 `2022FY`），`_format_report_period` 已存在但只在 YoY 格式化分支中使用。

测试服中文字体依赖系统安装的 CJK 字体，`chart.py` 的字体探测机制若全部失败，matplotlib 回退到 DejaVu Sans 导致中文乱码。

## Goals / Non-Goals

**Goals:**
- validation/reflection 产生��� warning 不混入用户可见答案（内部质量信号应保留在日志中，不展示给用户）
- 事实性同比 warning（白名单）仍可展示给用户
- 多子问题回答中，单行单列结果不重复子问题原文，直接输出值
- 多行���式化中 `report_period` 显示为人类可读格式（2022年、2024年半年度）
- 图表渲染在无系统 CJK 字体时有可用的回退方案

**Non-Goals:**
- 不改三层恢复机��本身的逻辑
- 不改 `QueryResult` 数据结构
- 不重构多子问题拆分逻辑

## Decisions

### 1. Warning 处理：仅保留事实性同比 warning 可见

**选择**：在 `pipeline.py` 中不再默认把 `result.warning` 追加到答案；仅当 warning 属于事实性同比提示时才展示给用户，其余 warning 只记录日志。注意：`research_qa.py` 的 `_format_sql_result` 当前并未追加 warning，无需修改该路径。

**事实性同比 warning 白名单**（当前仅包含以下文案，后续如扩展需同步更新文档与测��）：
- `上年同期值为零，无法计算同比增长率`
- `上年同期数据不存在，无法计算同比`

**替代方案**：彻底隐藏所有 warning → 会丢失同比无法计算这一类对答案解释有帮助的事实性提示。

**理由**：warning 中既有内部 reasoning，也有用户可理解的事实性说明，需做白名单区分而不是一刀切。

### 2. 单行单列输出：不带子问题文本

**选择**：在 `build_answer_content` 中，单���单列分支改为只输出字段中文标签 + 格式化后的值，不��接 question 参数。

**补充约束**：若字段标签未知（不在 `_FIELD_LABELS` 中），则回退为原字段名；返回值保留句号（与现有答案风格一致），但不得包含原始 question 文本。

**替代方案**：在 `_answer_sql` 层过滤子问题文本 → 但问题出在 `build_answer_content` 的设计，应在源头修。

### 3. report_period 格式化：复用已有函数

**选择**：在 `build_answer_content` 多行格式化的 identifiers 构建中，对 `report_period` 调用已有的 `_format_report_period`。

### 4. 字体回退：系统字体路���回退

**选择**：在 `chart.py` 字体探测失败后，尝试从系统路径 `/usr/share/fonts/truetype/wqy/wqy-microhei.ttc` 用 `FontProperties` 直���加载。若系统路径也���存在，log warning 并使用 matplotlib 默认字体��中文可能乱��，但不报错）。不在仓库中内嵌字体文件以避免仓库膨胀。

**替代方案**：仓库内嵌字体文件 → 当前仓库未包含该资源，且会增加体积与维护成本。

**理由**：与现有部署方式更一致，且不需要引入二进制资源。

## Risks / Trade-offs

- [白名单 warning 文案与代码不一致] → 缓解：spec/test 固定列出允许展示的文案，避免实现时随意用前缀匹配
- [系统路径字体在部分环境不存在] → 缓解：不存在时只记录 warning，不影响图表生成
- [单行单列结果失去上下文] → 缓解：字段标签需尽量使用中文标签；多轮上下��仍由问题列表本身提供
