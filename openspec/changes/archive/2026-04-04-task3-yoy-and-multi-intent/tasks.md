## 1. YoY 意图识别

- [x] 1.1 `_heuristic_intent()`: 检测"同比/增长率/同比增长/同比下降/增减"关键词，设置 `yoy: true`（排除"环比"——仅支持 FY 对 FY；排除单独的"增长/下降"——避免误触发两期对比查询）
- [x] 1.2 `_validate_intent()`: 为 `yoy` 字段添加 `setdefault(False)`
- [x] 1.3 `analyze()` LLM 路径: 新增 `_fix_yoy_intent()` post-fix 方法
- [x] 1.4 测试: "华润三九2024年净利润同比" → intent 含 `yoy: true`

## 2. YoY SQL 生成

- [x] 2.1 `_heuristic_sql()`: 当 `yoy: true` 时调用新的 `_build_yoy_sql()` 方法
- [x] 2.2 `_build_yoy_sql(table, fields, intent)`: 生成 self-join SQL — `a JOIN b ON stock_abbr AND b.report_period = '{year-1}FY'`（用显式 period 而非 LIKE），SELECT 当期值、上期值、`ROUND(..., 4) AS yoy_ratio`。支持多公司（`WHERE a.stock_abbr IN (...)`）以覆盖 Top N → YoY 组合场景
- [x] 2.3 空结果 fallback: 在 `_query_with_recovery` 中拦截 YoY 空结果，回退到单期查询 + warning
- [x] 2.4 测试: 验证生成的 SQL 语法正确、可执行、同比率计算准确

## 3. seek_table.md prompt 增强

- [x] 3.1 JSON schema 说明新增 `yoy`、`top_n`、`order_direction` 字段描述
- [x] 3.2 新增 few-shot 示例: "同比增长" → `yoy: true`
- [x] 3.3 新增 few-shot 示例: "top 10 企业" → `top_n: 10, order_direction: "DESC"`

## 3.5 ConversationManager.merge_intent 扩展

- [x] 3.5.1 `merge_intent()`: yoy 字段每轮独立判断，不从 slots 继承（避免跨轮泄漏）

## 4. 子问题间上下文传递

- [x] 4.1 `research_qa._answer_sql()`: 每个子问题完成后，从结果 rows 提取 stock_abbr 列表写入 `manager.slots["companies"]`
- [x] 4.2 添加条件: 仅当结果非空且 rows 含 stock_abbr 时注入
- [x] 4.3 测试: Top 10 结果的公司列表传递到"这些企业的同比"子问题

## 5. 端到端验证

- [ ] 5.1 B2001 端到端: top10 + 同比 + 最大增幅，三个子问题均应有实质性回答 <!-- 需 LLM API 跑完整端到端，heuristic 路径已通过 -->
- [x] 5.2 现有 pytest 不退化（29 passed）
- [x] 5.3 测试: 同比问句缺报告期时触发澄清
