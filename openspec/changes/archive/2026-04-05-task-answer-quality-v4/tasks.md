## 1. Warning 不混入用户答案

- [x] 1.1 `pipeline.py` `run_answer`：将 warning 展示逻辑改为白名单控制；非白名单 warning 仅 `logger.info("Query warning: %s", result.warning)` 记录日志
- [x] 1.2 定义允许展示给用户的事实性同比 warning 白名单，并统一在实现与测试中复用：
  - `上年同期值为零，无法计算同比增长率`
  - `上年同期数据不存在，无法计算同比`
- [x] 1.3 `research_qa.py`：确认 `_format_sql_result` 不追加 warning，必要时补日志但不改用户输出
- [x] 1.4 测试：验证 validation/reflection warning 不出现在答案中，白名单中的 YoY warning 仍展示

## 2. 单行单列结果不重复子问题文本

- [x] 2.1 `build_answer_content`：单行单列分支改为输出 `{field_label}{format_number(value, unit)}` 或等价自然语言，不包含 question 文本
- [x] 2.2 对含"同比"的单列字段（如 `net_profit_yoy_growth`），在 `build_answer_content` 单行单列分支中检查 field_label 是否含"同比"，若是则格式化为 `{base_name}同比{增长/下降}{abs(value):.2f}%`（参考多行分支 line 118-121 的同比格式化逻辑）
- [x] 2.3 补充字段标签缺失时的回退规则测试（使用原字段名，避免空字符串）
- [x] 2.4 测试：单行单列结果不含 question 文本

## 3. report_period 人类可读格式

- [x] 3.1 `build_answer_content` 多行格式化：identifiers 构建中对 `report_period` 调用 `_format_report_period`
- [x] 3.2 测试：多行结果中 `2022FY` 显示为 `2022年`，`2024Q3` 显示为 `2024年第三季度`

## 4. 图表中文字体回退

- [x] 4.1 `chart.py`：抽取可测试的字体解析/配置函数；字体探测全部失败后，尝试从系统路径 `/usr/share/fonts/truetype/wqy/wqy-microhei.ttc` 直接加载
- [x] 4.2 若系统路径也不存在，则记录 warning 并继续使用 matplotlib 默认字体，不抛异常
- [x] 4.3 测试：模拟"系统字体不存在 / 系统路径存在 / 两者都不存在"三种分支，至少验证配置过程不报错、缺字时会打日志

## 5. 回归验证

- [x] 5.1 更新现有 pipeline 测试：原"warning 一律追加"断言改为"仅白名单 warning 追加"
- [x] 5.2 现有 pytest 不退化
- [ ] 5.3 若本地无法执行附件4 + 附件6 全量测试，需在任务说明中标注为发布前人工验证项 <!-- 发布前人工验证项，本地 pytest 已全通过 -->
