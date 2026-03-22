## 1. 项目基础设施

- [x] 1.1 创建项目目录结构
- [x] 1.2 创建 requirements.txt
- [x] 1.3 实现 config.py
- [x] 1.4 创建 .env.example

## 2. LLM 客户端

- [x] 2.1 实现 src/llm/client.py
- [x] 2.2 实现重试逻辑
- [x] 2.3 冒烟测试

## 3. 官方 Schema + 公司信息

- [x] 3.1 实现 src/etl/schema.py（从附件3 动态读取）
- [x] 3.2 实现公司信息加载
- [x] 3.3 验证建表字段
- [x] 3.4 字段级单位元数据

## 4. PDF 表格定位与解析（重写，参考 FinGLM）

- [ ] 4.1 重写 pdf_parser.py 的表格分类逻辑：用**表格自身内容**分类（前 3 行单元格），不是页面文本。参考 `references/FinGLM/code/馒头科技/mantoutech/financial_state.py` 的 find_match_page()
- [ ] 4.2 实现确认关键词验证：资产负债表确认"货币资金"，利润表确认"营业收入"，现金流量表确认"销售商品"。参考馒头科技的 required_post_keywords
- [ ] 4.3 实现无效关键词过滤：排除"母公司资产负债表"/"母公司利润表"等非合并报表
- [ ] 4.4 深交所文件名解析（已实现，验证正确性）
- [ ] 4.5 上交所首页标题解析 + 发布日期兜底（已实现，验证正确性）
- [ ] 4.6 上交所同日多 PDF 区分：摘要跳过，完整报告入库
- [ ] 4.7 跨页表格合并：同类型+相邻页合并，同页不合并，未分类紧邻表继承类型
- [ ] 4.8 核心业绩指标从 PDF 前 15 页单独提取（"主要会计数据和财务指标"章节）
- [ ] 4.9 测试：金花股份 2023FY 年报 page 84 的同页双表能正确区分
- [ ] 4.10 测试：两家公司全部 PDF → 表格类型分类正确率 > 90%

## 5. 别名字典与字段映射（大幅扩充，参考南哪都队）

- [ ] 5.1 从 `references/FinGLM/code/南哪都队/.../excel_process.py` 的 features_alias 提取财务术语别名，适配到官方 4 张表
- [ ] 5.2 实现 _normalize_label()：去序号前缀（参考南哪都队 rm_prefix()）+ 去括号注释。确保串进匹配主路径
- [ ] 5.3 income_sheet 别名全覆盖（含所有序号变体）
- [ ] 5.4 balance_sheet 别名全覆盖
- [ ] 5.5 cash_flow_sheet 别名全覆盖
- [ ] 5.6 core_performance 别名全覆盖
- [ ] 5.7 字段级单位换算：参考馒头科技 get_unit()
- [ ] 5.8 同比/环比/占比派生字段计算
- [ ] 5.9 测试：华润三九 2023FY income_sheet 字段覆盖率 > 80%
- [ ] 5.10 测试：金花股份 2023FY income_sheet 字段覆盖率 > 80%

## 6. 数据校验

- [x] 6.1 勾稽关系校验
- [x] 6.2 跨表一致性校验
- [x] 6.3 格式校验
- [ ] 6.4 致命错误阻塞入库，非致命记 warning

## 7. 数据入库 + Pipeline

- [x] 7.1 loader.py INSERT OR REPLACE
- [x] 7.2 pipeline.py --task etl 全自动
- [x] 7.3 per-file try/except 错误隔离
- [ ] 7.4 集成测试：全部 PDF → 4 张表关键字段非 None

## 8. Prompt 模板

- [x] 8.1 prompt loader
- [ ] 8.2 重写 seek_table.md：完整字段列表 + 中文说明。参考 chatbot_financial_statement/agent/prompt/
- [ ] 8.3 重写 generate_sql.md：完整 CREATE TABLE + 20-30 个 few-shot SQL 示例
- [x] 8.4 answer.md
- [x] 8.5 clarify.md
- [x] 8.6 chart_select.md

## 9. Text2SQL 查询引擎

- [x] 9.1 两步式基础实现
- [x] 9.2 Schema 从 etl/schema.py 动态生成
- [x] 9.3 公司列表从数据库动态获取
- [ ] 9.4 SQL 参数化防注入
- [ ] 9.5 手工 few-shot SQL 示例（20-30 个）
- [ ] 9.6 3 层错误恢复（参考 chatbot_financial_statement debug→correction→reflection）

## 10. 多轮对话

- [x] 10.1 ConversationManager 槽位继承
- [x] 10.2 意图澄清
- [x] 10.3 趋势查询不要求 periods

## 11. 图表 + 回答格式化

- [x] 11.1 matplotlib 折线/柱状/饼图
- [x] 11.2 规则式图表选择
- [x] 11.3 安全图表数据构造
- [ ] 11.4 result_2.xlsx 格式验证

## 12. Pipeline + Gradio

- [x] 12.1 pipeline.py --task etl
- [x] 12.2 pipeline.py --task answer --questions xlsx
- [x] 12.3 app.py Gradio 界面
- [ ] 12.4 端到端测试：B1001 + B1002 正确回答
