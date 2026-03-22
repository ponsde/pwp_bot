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
