### Debug 的回复（Round 1）
- 判断：不通过（已修复）
- 原因：查询链路存在 7 个阻塞/中影响问题：Text2SQL 使用自造简化 schema、公司识别硬编码、多轮追问上下文无法继承、answer 结果缺少图形格式列、数值单位格式化错误、pipeline 仍按 JSON 读题且未按题目分组复用会话。
- 修改（如有）：
  - src/query/text2sql.py — 改为从 `src/etl/schema.py` 动态构建 4 张官方表完整 `CREATE TABLE`，并从数据库 `SELECT DISTINCT stock_abbr` 动态识别公司；同时让 `analyze()` 合并会话槽位，修复追问时 company/metric/period 继承。
  - src/query/conversation.py — 为 ConversationManager 增加 `slots` 与 `merge_intent()`，保存并复用上轮已确定的 tables/fields/companies/periods。
  - pipeline.py — answer 任务改为读取附件4格式 xlsx，新增 `--questions` 参数，并按每一行问题数组分组创建独立 ConversationManager，组内多轮共享上下文。
  - src/query/answer.py — 修正 `format_number()` 为以“万元”为基准格式化（≥10000万元显示亿元），并为 `result_2.xlsx` 增加“图形格式”列。
  - tests/test_answer.py — 同步更新断言，覆盖“图形格式”列。
  - tests/test_pipeline.py — 同步更新为读取附件4 xlsx 的端到端入口。

### Debug 的回复（Round 2）
- 判断：不通过（已修复）
- 原因：本轮审查发现 3 个问题：
  1. `_query_with_recovery()` 在第 2/3 层重试后没有再次检查失败结果，导致“最多 1 次重试”表面满足，但最终可能悄悄返回错误结果。
  2. `_query_with_recovery()` 仅用 `dict(intent)` 做浅拷贝，若后续链路修改 list 字段会破坏 immutable 约束。
  3. 无 LLM 模式下的结果校验只检查首行字段，无法发现返回了错误公司/报告期的成功 SQL。
- 修改（如有）：
  - `src/query/text2sql.py` — 引入 `copy.deepcopy()` 保护输入 intent 不被恢复链路修改；在第 2 层和第 3 层各自的单次重试后立即再次校验，若仍失败则抛出用户可读错误，避免错误结果被静默返回；增强启发式 `_validate_result()`，补充对 `stock_abbr` / `report_period` 的结果一致性检查。
  - `tests/test_text2sql.py` — 修正第 2 层 stub 测试，使其真正覆盖“第一次校验失败、单次重试后成功”的流程；新增“第 2 层最多重试 1 次后失败返回错误”“第 3 层最多重试 1 次后失败返回错误”“恢复流程不修改传入 intent”测试，覆盖本轮修复点。
