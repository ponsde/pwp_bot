## Why

全量测试（附件4 + 附件6）暴露四个答案质量问题：1) B1001 第二轮回答尾部带了一大段 validation/reflection 内部 warning，用户不该看到；2) B2001 多子问题回答中，子问题原文被拼进了最终答案（"在这些企业中...是哪家企业？：金花股份"）；3) 多行结果中 report_period 显示原始格式 "2022FY" 而不是 "2022年"；4) 测试服图表中文字体缺失导致乱码。

## What Changes

- 过滤 `build_answer_content` / `_format_sql_result` 输出中的内部 warning（`validate_result` 和 `reflect` 层产生的注释不应混入用户可见的答案内容）
- 修复 `_answer_sql` 多子问题拼接：子问题文本不应作为 answer 内容的一部分出现
- 在多行格式化中调用 `_format_report_period` 将 `2022FY` → `2022年`、`2024HY` → `2024年半年度`
- 图表渲染增加字体回退机制，确保无 CJK 字体环境也能正常显示中文

## Capabilities

### New Capabilities
- `chart-font-fallback`: 图表渲染的中文字体回退机制，当系统无 CJK 字体时使用 matplotlib 内置字体或自带字体文件

### Modified Capabilities
- `answer-formatter`: 多行格式化中 report_period 需要做人类可读转换；过滤内部 warning 文本
- `text2sql`: validation/reflection warning 不应混入用户答案

## Impact

- `src/query/answer.py` — `build_answer_content` 多行格式化中的 report_period 转换
- `src/knowledge/research_qa.py` — `_answer_sql` 子问题拼接逻辑（此模块当前不追加 warning，无需修改 warning 处理；仅 `pipeline.py` 需要改）
- `src/query/text2sql.py` — warning 字段的传播方式（确保不混入 answer 内容）
- `src/query/chart.py` — 字体回退机制
- 测试：需新增 warning 过滤、report_period 格式化、子问题拼接的测试用例
