## Context

text2sql 引擎当前只能生成单表 SELECT 查询。同比/环比需要同一指标跨两个报告期的数据做差值除法，必须用 self-join 或 window function。SQLite 支持 window function（3.25+），但 self-join 更直观、更容易让 LLM 生成正确结果。

多子问题编排方面，`research_qa._answer_sql()` 通过 `split_multi_intent()` 拆分复合问题后，每个子问题独立调用 `text2sql.query()`，子问题间没有结果传递。"这些企业"这类指代无法消解。

## Goals / Non-Goals

**Goals:**
- 同比 SQL：heuristic 路径能为"同比/环比/增长率"意图生成 self-join SQL
- 同比 SQL：LLM 路径通过 prompt 增强 + intent 字段扩展支持同比
- 子问题编排：前一子问题的 SQL 结果（如公司列表）自动注入后续子问题的 conversation slot
- B2001 端到端从 3/10 提升到 7/10+

**Non-Goals:**
- 不支持复合同比（如"同比增长率的同比"）
- 不支持自定义基期（默认上一年 FY 对 FY）
- 不重构 split_multi_intent 的拆分策略
- 不改 ETL 或 OV 索引

## Decisions

### 1. Self-join vs Window Function

**选择：Self-join**
- 理由：`SELECT a.field, b.field, (a.field - b.field)/b.field FROM table a JOIN table b ON a.stock_abbr = b.stock_abbr AND a.report_year = b.report_year + 1` 对 LLM 更容易理解和生成
- 替代方案：`LAG() OVER (PARTITION BY stock_abbr ORDER BY report_year)` 更简洁，但 LLM 生成 window function 的准确率较低
- SQLite 兼容性：两种都支持，self-join 兼容性更好

### 2. Intent 扩展方式

**选择：在 intent dict 中新增 `yoy` 布尔字段**
- `yoy: true` 表示需要同比计算
- `_heuristic_intent` 识别"同比/增长率/同比增长/同比下降/增减"关键词（排除"环比"和单独的"增长/下降"，避免误触发）
- `generate_sql` 看到 `yoy: true` 时切换到 self-join 模板
- 替代方案：让 LLM 直接生成 self-join SQL 不加 intent 字段——但 heuristic 路径无法受益

### 3. 子问题上下文注入方式

**选择：在 `_answer_sql` 循环中，将前一子问题的结果公司列表写入 ConversationManager.slots["companies"]**
- 当子问题包含"这些"/"其"/"上述"等指代词时，从 slots 中取出公司列表注入
- 替代方案：把前一子问题的完整结果拼入后续子问题文本——太长，且 heuristic 路径无法解析

## Risks / Trade-offs

- [Self-join 可能返回空] 如果上一年没有对应 FY 数据，join 结果为空 → 缓解：fallback 为只返回当年数据 + warning
- [子问题指代消解不完美] 只处理公司列表传递，不处理指标/期间的指代 → 可接受，覆盖最常见场景
- [Heuristic 同比仅支持 FY 对 FY] 不支持季度同比（Q3 vs 去年 Q3）→ 4.25 测试题目以年度为主，暂可接受
