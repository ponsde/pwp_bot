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
- [ ] 3.4 为每个字段补充单位元数据（元 / 万元 / % / 比率），供转换和校验复用

## 4. PDF 解析（任务一核心 P0）

- [ ] 4.1 实现 src/etl/pdf_parser.py：pdfplumber 提取 PDF 中的表格与页面文本，返回结构化 page/table 对象
- [ ] 4.2 实现深交所文件名解析：从 `华润三九：2023年年度报告.pdf` 提取 stock_abbr + report_period + report_year
- [ ] 4.3 实现上交所文件名解析：从 `600080_20240427_0WKP.pdf` 提取 stock_code；**优先从 PDF 首页标题识别** 报告类型与报告期，发布日期只作为兜底信息
- [ ] 4.4 实现上交所摘要识别：对“年度报告摘要 / 半年度报告摘要”等文件打标并默认跳过入库
- [ ] 4.5 实现跨页表格合并：处理合并单元格、跨页表格拼接
- [ ] 4.6 测试：华润三九 2023 年报 PDF 能提取出主要会计数据区、资产负债表、利润表、现金流量表
- [ ] 4.7 测试：金花股份 2023 年报 PDF 能提取出主要会计数据区、资产负债表、利润表、现金流量表
- [ ] 4.8 测试：验证上交所同一日期下多份 PDF 能正确区分“完整版报告 / 摘要 / 季报”

## 5. 表格字段映射

- [ ] 5.1 实现 src/etl/table_extractor.py：中文指标名 → 官方英文字段名映射字典
- [ ] 5.2 将映射拆分为 4 张官方表分别维护，不混用同名字段在不同表的含义
- [ ] 5.3 覆盖 4 张表的常见字段别名（从示例 PDF 中收集实际出现的中文名）
- [ ] 5.4 实现字段级单位换算：依据附件3字段单位逐项处理；不得使用“默认全部÷10000”的粗规则
- [ ] 5.5 实现表类型识别：从表格标题和内容判断属于 balance_sheet / income_sheet / cash_flow_sheet / core_performance_indicators_sheet
- [ ] 5.6 为 core_performance_indicators_sheet 单独实现抽取逻辑：从“主要会计数据 / 主要财务指标 / 分季度主要财务指标”中取值
- [ ] 5.7 实现同比、环比、占比等派生字段计算规则
- [ ] 5.8 对未命中字段输出 warning 与 unmapped 清单；LLM 推荐仅作为可选增强，不阻塞主链路
- [ ] 5.9 测试：华润三九年报的利润表关键字段能正确映射到 income_sheet
- [ ] 5.10 测试：金花股份年报的核心业绩指标关键字段能正确映射到 core_performance_indicators_sheet

## 6. 数据校验

- [ ] 6.1 实现 src/etl/validator.py：勾稽关系校验（资产=负债+权益，营业利润勾稽）
- [ ] 6.2 实现跨表一致性校验（income_sheet.净利润 ≈ core_performance.净利润）
- [ ] 6.3 实现格式校验（report_period 格式、字段单位转换后类型正确）
- [ ] 6.4 校验不通过时记录警告但不阻塞入库

## 7. 数据入库

- [ ] 7.1 实现 src/etl/loader.py：以 `(stock_code, report_period)` + 表名为幂等键执行 INSERT OR REPLACE
- [ ] 7.2 仅对完整版报告入库，摘要文件跳过并记录原因
- [ ] 7.3 集成测试：华润三九 + 金花股份全部**完整版** PDF → 解析 → 映射 → 校验 → 入库 → SQL 查询验证

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
- [ ] 9.3 强制 SQL 使用标准化 `report_period` 值（如 `2025Q3`），避免 `Q3 + report_year` 的混合表达
- [ ] 9.4 实现 SQL 执行 + 失败重试（最多 2 次）
- [ ] 9.5 实现用户友好失败分支：公司未找到、字段未识别、期间缺失、空结果

## 10. 多轮对话

- [ ] 10.1 实现 src/query/conversation.py：维护会话历史，追问时拼接上下文
- [ ] 10.2 实现意图澄清：检测缺失关键信息 → 返回澄清问题而非猜测

## 11. 图表生成

- [ ] 11.1 实现 src/query/chart.py：matplotlib 折线图/柱状图/饼图
- [ ] 11.2 先实现规则式图表类型选择（趋势→折线，对比→柱状，占比→饼）
- [ ] 11.3 图表保存到 result/{编号}_{序号}.jpg

## 12. 回答格式化

- [ ] 12.1 实现 src/query/answer.py：LLM 生成分析结论文本 + 数字格式化（万元/亿元）
- [ ] 12.2 实现 JSON 输出格式：[{Q, A: {content, image}}] 按附件7
- [ ] 12.3 实现 result_2.xlsx 生成：编号/问题/SQL/图形格式/回答

## 13. Pipeline + Gradio

- [ ] 13.1 实现 pipeline.py：`--task etl` 一键 PDF→DB，`--task answer` 一键答题→xlsx
- [ ] 13.2 实现 app.py：Gradio Chat 界面 + SQL 展示 + 图表展示
- [ ] 13.3 端到端测试：附件4 的 B1001 + B1002 能正确回答，输出 result_2.xlsx
