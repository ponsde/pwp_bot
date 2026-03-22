## 1. 项目基础设施

- [ ] 1.1 创建项目目录结构（src/etl, src/query, src/llm, src/viking, src/prompts, data/raw, data/db, data/processed, tests）
- [ ] 1.2 创建 requirements.txt（akshare, pdfplumber, openai, gradio, openviking, python-dotenv, pandas）
- [ ] 1.3 实现 config.py：从 .env 读取 LLM/Embedding API 配置 + OV 配置（embedding endpoint/model/dimension），暴露项目路径，缺少必需变量时 fail fast
- [ ] 1.4 创建 .env.example 文档化所有必需环境变量（含 OV embedding 相关）

## 2. LLM 客户端

- [ ] 2.1 实现 src/llm/client.py：chat_completion 函数（messages → str），支持 temperature 和 JSON mode（含 fallback：JSON mode 不可用时用正则提取）
- [ ] 2.2 实现 embedding 函数（texts → list[list[float]]），调用 BAAI/bge-m3
- [ ] 2.3 实现重试逻辑：429/5xx/timeout 自动重试 3 次，指数退避
- [ ] 2.4 编写 LLM client 冒烟测试（真实 API 调用验证连通性）

## 3. ETL 数据管线

- [ ] 3.1 实现 src/etl/api_fetcher.py：用 ak.stock_info_a_code_name() 获取 A 股股票列表（code, name 两列），写入 companies 表
- [ ] 3.2 实现获取单只股票三张财务报表（ak.stock_financial_report_sina），本地缓存为 CSV。注意：返回格式是多报告期行 x 多指标列，报告日为字符串如 "20231231"
- [ ] 3.3 实现批量拉取：指定股票代码子集（Phase 1 先做 50-100 家），显示进度，单个失败不中断，请求间添加 sleep 避免限流，支持断点续传（跳过已缓存）
- [ ] 3.4 实现 src/etl/schema.py：创建 SQLite 三表 — companies(stock_code, company_name)、financial_data(stock_code, report_date, statement_type, item_name, value) + UNIQUE 约束、item_mapping(item_name, alias, statement_type) + 索引
- [ ] 3.5 实现 src/etl/loader.py：逐行（报告期）逐列（指标）展开 DataFrame → 插入 financial_data，跳过 NaN，INSERT OR IGNORE 幂等。支持过滤仅年报（report_date 以 "1231" 结尾）
- [ ] 3.6 构建 item_mapping 初始数据：从 AKShare 列名提取规范名，手动添加常用别名（营收→营业收入，净利→净利润 等）
- [ ] 3.7 编写 ETL 集成测试：拉取茅台数据 → 入库 → 验证 SQL "SELECT value FROM financial_data WHERE stock_code='600519' AND item_name='营业收入' AND report_date='20231231'" 返回正确值

## 4. PDF 解析

- [ ] 4.1 实现 src/etl/pdf_parser.py：pdfplumber 逐页提取文本，返回 list[str]，处理空页（作为 OV 导入的 fallback 方案）
- [ ] 4.2 实现批量处理：扫描 data/raw/ 目录，输出 .txt 文件到 data/processed/
- [ ] 4.3 下载 3 份练手 PDF（茅台、比亚迪、平安银行）到 data/raw/
- [ ] 4.4 编写 PDF 解析测试：验证茅台年报可正常解析出文本

## 5. Prompt 模板

- [ ] 5.1 实现 src/prompts/loader.py：加载 .md 模板文件，支持 {variable} 占位符替换
- [ ] 5.2 编写 src/prompts/seek_database.md：指导 LLM 从用户问题中提取 companies/accounts/years 的 JSON，含示例
- [ ] 5.3 编写 src/prompts/generate_sql.md：提供 schema + 映射结果 + 示例数据，指导 LLM 生成 SQL（用 ```sql``` 包裹）
- [ ] 5.4 编写 src/prompts/answer.md：指导 LLM 从 SQL 结果生成自然语言回答，格式化大数字为万元/亿元

## 6. Text2SQL 查询引擎

- [ ] 6.1 实现 src/query/text2sql.py Step1：调用 seek_database prompt → 解析 JSON（含 fallback 正则提取）→ 查 companies 表模糊匹配 stock_code → 查 item_mapping 匹配 item_name
- [ ] 6.2 实现 Step2：拼装 schema snapshot（CREATE TABLE 语句 + 映射结果 + 示例数据行）→ 调用 generate_sql prompt → 从 ```sql``` 代码块提取 SQL
- [ ] 6.3 实现 SQL 执行 + 失败重试：执行 SQL，失败时将错误反馈给 LLM 重新生成（最多 2 次）
- [ ] 6.4 实现答案生成：SQL 结果 + 用户问题 → 调用 answer prompt → 返回自然语言回答
- [ ] 6.5 编写端到端测试："贵州茅台2023年营业收入是多少？" → 正确数值答案

## 7. OpenViking Resource

- [ ] 7.1 创建 ov.conf：embedded 模式，配置 embedding（provider: "openai", model: "BAAI/bge-m3", api_base, api_key, dimension: 1024）和数据路径
- [ ] 7.2 实现 src/viking/client.py：OV 客户端初始化封装（ov.OpenViking + initialize）
- [ ] 7.3 实现 src/viking/resource.py：优先直接用 add_resource(path=<pdf_path>) 让 OV 解析 PDF；如果失败则 fallback 到导入 pdfplumber 提取的 .txt 文件
- [ ] 7.4 验证 OV find 检索：导入茅台年报后，find("贵州茅台发展战略", limit=3) 返回 .resources 列表，各项有 .uri 和 .score

## 8. Gradio 界面

- [ ] 8.1 实现 app.py：Gradio Chat 界面，输入框 + 聊天历史
- [ ] 8.2 接入 Text2SQL 管线：用户提问 → text2sql 处理 → 显示答案
- [ ] 8.3 添加 SQL 展示区：可折叠面板显示生成的 SQL 查询
- [ ] 8.4 错误处理：查询失败时显示友好提示而非 traceback
