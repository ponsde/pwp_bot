## 1. 项目基础设施

- [ ] 1.1 创建项目目录结构（src/etl, src/query, src/knowledge, src/llm, src/viking, src/prompts, data/, result/, tests/）
- [ ] 1.2 创建 requirements.txt（pdfplumber, openai, gradio, matplotlib, pandas, openpyxl, python-dotenv, faiss-cpu）
- [ ] 1.3 实现 config.py：从 .env 读取 LLM API 配置，暴露项目路径，fail fast
- [ ] 1.4 创建 .env.example

## 2. LLM 客户端

- [ ] 2.1 实现 src/llm/client.py：chat_completion（支持 temperature、JSON mode + regex fallback）
- [ ] 2.2 实现重试逻辑：429/5xx/timeout 自动重试 3 次，指数退避
- [ ] 2.3 冒烟测试：验证 API 连通性

## 3. 官方 Schema + 公司信息

- [ ] 3.1 实现 src/etl/schema.py：按附件3 创建 4 张 SQLite 表（core_performance_indicators_sheet, balance_sheet, income_sheet, cash_flow_sheet），字段名/类型完全对齐
- [ ] 3.2 实现公司信息加载：读取附件1 xlsx，建立 stock_code ↔ stock_abbr 映射
- [ ] 3.3 验证：建表后检查字段与附件3 一致

## 4. PDF 解析（任务一核心 P0）

- [ ] 4.1 实现 src/etl/pdf_parser.py：pdfplumber 提取 PDF 中的表格，返回 list of DataFrame
- [ ] 4.2 实现深交所文件名解析：从 "华润三九：2023年年度报告.pdf" 提取 stock_abbr + report_period + report_year
- [ ] 4.3 实现上交所文件名解析：从 "600080_20230428_FQ2V.pdf" 提取 stock_code + 从发布日期推断 report_period
- [ ] 4.4 实现跨页表格合并：处理合并单元格、跨页表格拼接
- [ ] 4.5 测试：华润三九 2023 年报 PDF 能提取出资产负债表、利润表、现金流量表

## 5. 表格字段映射

- [ ] 5.1 实现 src/etl/table_extractor.py：中文指标名 → 官方英文字段名映射字典
- [ ] 5.2 覆盖 4 张表的所有字段别名（从示例 PDF 中收集实际出现的中文名）
- [ ] 5.3 实现单位换算：元→万元（÷10000），百分比处理，每股指标保持元
- [ ] 5.4 实现 LLM fallback：映射字典未命中时调用 LLM 推荐字段
- [ ] 5.5 实现表类型识别：从表格标题判断属于哪张官方表（资产负债表/利润表/现金流量表/业绩指标）
- [ ] 5.6 测试：华润三九年报的利润表所有字段能正确映射到 income_sheet 的字段

## 6. 数据校验

- [ ] 6.1 实现 src/etl/validator.py：勾稽关系校验（资产=负债+权益，营业利润勾稽）
- [ ] 6.2 实现跨表一致性校验（income_sheet.净利润 ≈ core_performance.净利润）
- [ ] 6.3 实现格式校验（report_period 格式、数值非负）
- [ ] 6.4 校验不通过时记录警告但不阻塞入库

## 7. 数据入库

- [ ] 7.1 实现 src/etl/loader.py：INSERT OR REPLACE by (stock_code, report_period)
- [ ] 7.2 集成测试：华润三九 + 金花股份全部 PDF → 解析 → 映射 → 校验 → 入库 → SQL 查询验证

## 8. Prompt 模板

- [ ] 8.1 实现 src/prompts/loader.py：加载 .md 模板，{variable} 替换
- [ ] 8.2 编写 src/prompts/seek_table.md：从问题提取 tables/fields/companies/periods 的 JSON
- [ ] 8.3 编写 src/prompts/generate_sql.md：完整 Schema + 映射结果 → SQL（```sql``` 包裹）
- [ ] 8.4 编写 src/prompts/answer.md：SQL 结果 → 自然语言回答 + 数字格式化
- [ ] 8.5 编写 src/prompts/clarify.md：检测缺失信息 → 生成澄清问题
- [ ] 8.6 编写 src/prompts/chart_select.md：判断是否需要图表 + 图表类型

## 9. Text2SQL 查询引擎

- [ ] 9.1 实现 src/query/text2sql.py Step1：调用 seek_table prompt → 解析 JSON → 验证公司/字段存在
- [ ] 9.2 实现 Step2：拼完整 Schema + Step1 结果 → 调用 generate_sql prompt → 提取 SQL
- [ ] 9.3 实现 SQL 执行 + 失败重试（最多 2 次）
- [ ] 9.4 实现用户友好失败分支：公司未找到、字段未识别、期间缺失、空结果

## 10. 多轮对话

- [ ] 10.1 实现 src/query/conversation.py：维护会话历史，追问时拼接上下文
- [ ] 10.2 实现意图澄清：检测缺失关键信息 → 返回澄清问题而非猜测

## 11. 图表生成

- [ ] 11.1 实现 src/query/chart.py：matplotlib 折线图/柱状图/饼图
- [ ] 11.2 实现图表类型自动选择（LLM 或规则：趋势→折线，对比→柱状，占比→饼）
- [ ] 11.3 图表保存到 result/{编号}_{序号}.jpg

## 12. 回答格式化

- [ ] 12.1 实现 src/query/answer.py：LLM 生成分析结论文本 + 数字格式化（万元/亿元）
- [ ] 12.2 实现 JSON 输出格式：[{Q, A: {content, image}}] 按附件7
- [ ] 12.3 实现 result_2.xlsx 生成：编号/问题/SQL/图形格式/回答

## 13. Pipeline + Gradio

- [ ] 13.1 实现 pipeline.py：`--task etl` 一键 PDF→DB，`--task answer` 一键答题→xlsx
- [ ] 13.2 实现 app.py：Gradio Chat 界面 + SQL 展示 + 图表展示
- [ ] 13.3 端到端测试：附件4 的 B1001 + B1002 能正确回答，输出 result_2.xlsx
