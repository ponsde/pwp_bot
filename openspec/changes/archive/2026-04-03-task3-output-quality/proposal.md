# 任务三输出质量二期

## 背景

task3-research-polish 修复了 references 路径、答案去重、warning 隐藏、hybrid 格式和图表渲染。端到端跑附件6 发现还有几个影响评分的问题。

## 问题清单

### P0 — 必须修

1. **refs text 含英文 VLM 摘要**
   - OV 对某些 chunk 生成了英文摘要（"This file is an industry commentary..."）
   - 这些英文文本出现在 references[].text 里，不符合中文研报引用预期
   - 方案：在 retriever 或 ov_adapter 层过滤/跳过英文为主的 text

2. **"近三年"年份解析偏移**
   - B2003 Q1 问"近三年"，SQL 生成 `IN ('2023FY','2024FY','2025FY')`
   - 实际数据最新只到 2024FY，2025FY 不存在，导致只查到 2 年
   - 方案：text2sql 的 analyze() 根据 DB 中实际存在的最大 report_year 推算"近N年"，而非假设当前年份

3. **图表 Y 轴科学计数法**
   - bar chart 显示 `1e6`、`2,761,661` 等原始数值
   - 财务数据应显示"亿元"单位，Y 轴 `180.79` 而非 `1807946`
   - 方案：render_chart 时自动检测量级，转换为万元/亿元并标注单位

### P1 — 该做

4. **B2001 top N 聚合查询失败**
   - 问"利润最高的top10企业"返回了澄清问题
   - text2sql 不支持跨公司聚合 + 排序 + LIMIT 的复合查询
   - 方案：在 analyze() 中识别"top N"/"排名"意图，生成带 ORDER BY + LIMIT 的 SQL

5. **答案口吻不一致**
   - B2002 RAG 答案有"如果你需要，我可以继续帮你..."这类对话式尾巴
   - 作为交作业的 result_3.xlsx 答案应更正式
   - 方案：在 _compose_rag_answer 的 prompt 中加约束"不要反问用户"

## 不做

- 不改 OV 索引策略或 VLM 配置
- 不改 ETL 管线
- 不增加额外数据源
