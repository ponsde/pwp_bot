## 1. 英文 refs 过滤

- [x] 1.1 ov_adapter.py 或 retriever.py：检测 text 是否以英文为主（中文字符占比 < 30%），是则跳过或降权
- [x] 1.2 确保过滤后 references 数量仍 >= 1（不能全过滤掉）

## 2. "近N年"年份解析

- [x] 2.1 text2sql analyze()：识别"近三年/近五年"等相对时间表述
- [x] 2.2 根据 DB 中目标公司实际存在的最大 report_year 向前推算，而非硬编码当前年份
- [x] 2.3 测试：华润三九"近三年"应解析为 2022FY/2023FY/2024FY

## 3. 图表单位优化

- [x] 3.1 chart.py render_chart：检测数值量级，自动转为万元/亿元
- [x] 3.2 Y 轴标签显示单位（如"金额（亿元）"）
- [x] 3.3 数据标签同步转换（显示 247.39 而非 2473896）

## 4. Top N 聚合查询

- [x] 4.1 text2sql analyze()：识别"top N"/"排名前N"/"最高/最低的N家"意图
- [x] 4.2 generate_sql()：生成 ORDER BY + LIMIT N 语句
- [x] 4.3 测试：验证 top 10 查询能生成正确 SQL

## 5. RAG 答案口吻

- [x] 5.1 _compose_rag_answer prompt 中加约束：不反问用户、不说"如果你需要"
- [x] 5.2 保持答案简洁正式

## 6. 验证

- [x] 6.1 端到端跑附件6，确认输出质量
- [x] 6.2 现有 pytest 不退化（67 passed，3 failed 均为 ETL PDF 集成测试，与本变更无关）
