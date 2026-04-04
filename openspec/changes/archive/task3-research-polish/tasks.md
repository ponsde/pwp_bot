## 1. References 输出修复

- [x] 1.1 retriever.py：将 OV `viking://resources/...` URI 映射回原始 PDF 路径（用 stem 匹配 known_papers）
- [x] 1.2 retriever.py：refs 的 text 截取命中段落关键片段（200-500 字），不是整个 markdown 文件
- [x] 1.3 paper_path 使用相对路径格式（`./附件5：研报数据/...`）

## 2. 答案去重 & 去 warning

- [x] 2.1 排查 B2003 Q1 答案重复原因，修复（SQL 结果只应出现一次）
- [x] 2.2 research_qa.py：_format_sql_result 不输出 warning 到最终答案
- [x] 2.3 Hybrid 路径：Q2 归因答案不重复 Q1 的 SQL 数据

## 3. 图表渲染

- [x] 3.1 确认 research pipeline 对 chart_type != "无" 时生成图表 jpg
- [x] 3.2 如未生成，在 run_research() 中接入 render_chart

## 4. 测试验证

- [x] 4.1 端到端跑附件6 三道题，确认输出质量
- [x] 4.2 现有 pytest 不退化
