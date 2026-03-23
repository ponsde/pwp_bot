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

## 4. PDF 表格定位与解析

- [x] 4.1 表格分类用表格自身内容（前 3 行单元格）+ 确认关键词
- [x] 4.2 确认关键词验证（货币资金/营业收入/销售商品）
- [x] 4.3 无效关键词过滤（排除母公司报表）
- [x] 4.4 深交所文件名解析
- [x] 4.5 上交所首页标题解析 + 发布日期兜底
- [x] 4.6 上交所同日多 PDF 区分：摘要跳过
- [x] 4.7 跨页表格合并：同类型+相邻页合并，同页不合并，未分类紧邻表继承类型
- [x] 4.8 核心业绩指标从 PDF 前部页面提取
- [x] 4.9 金花股份同页双表正确区分
- [x] 4.10 全页扫描（不跳过中间页）

## 5. 别名字典与字段映射

- [x] 5.1 从南哪都队 features_alias 适配 86+ 别名到官方 4 张表
- [x] 5.2 _normalize_label：去序号前缀 + 去所有括号注释，串进匹配主路径
- [x] 5.3 income_sheet 别名覆盖（83.3% 字段覆盖率）
- [x] 5.4 balance_sheet 别名覆盖（62.2%，负债/权益合计跨页待改进）
- [x] 5.5 cash_flow_sheet 别名覆盖（77.2%）
- [x] 5.6 core_performance 别名覆盖（10.3%，季报提取待改进）
- [x] 5.7 字段级单位换算（元/万元/千元/百万元，默认元）
- [x] 5.8 派生字段计算（资产负债率、现金流占比）
- [x] 5.9 华润三九 2023FY income_sheet 覆盖率 > 80% ✓
- [x] 5.10 金花股份 2023FY income_sheet 覆盖率 > 80% ✓

## 6. 数据校验

- [x] 6.1 勾稽关系校验（1% 相对容差）
- [x] 6.2 跨表一致性校验
- [x] 6.3 格式校验
- [x] 6.4 致命错误（勾稽不平）阻塞入库，缺字段记 warning 继续

## 7. 数据入库 + Pipeline

- [x] 7.1 loader.py INSERT OR REPLACE
- [x] 7.2 pipeline.py --task etl 全自动
- [x] 7.3 per-file try/except 错误隔离
- [x] 7.4 集成测试：36 PDF → 24 loaded, 12 skipped, 0 rejected

## 8. Prompt 模板

- [x] 8.1 prompt loader
- [x] 8.2 seek_table.md（完整字段列表 + few-shot 意图解析）
- [x] 8.3 generate_sql.md（完整 Schema + few-shot SQL）
- [x] 8.4 answer.md
- [x] 8.5 clarify.md
- [x] 8.6 chart_select.md

## 9. Text2SQL 查询引擎

- [x] 9.1 两步式基础实现
- [x] 9.2 Schema 从 etl/schema.py 动态生成
- [x] 9.3 公司列表从数据库动态获取 + 公司不存在友好提示
- [x] 9.4 SQL 安全检查（禁止 DROP/DELETE/UPDATE/INSERT，禁止多语句）
- [x] 9.5 few-shot SQL 示例（在 prompt 模板中）
- [ ] 9.6 3 层错误恢复（仅实现第 1 层自动 debug，2-3 层待 Phase 2）

## 10. 多轮对话

- [x] 10.1 ConversationManager 槽位继承
- [x] 10.2 意图澄清
- [x] 10.3 趋势查询不要求 periods

## 11. 图表 + 回答格式化

- [x] 11.1 matplotlib 折线/柱状/饼图 + CJK 字体支持
- [x] 11.2 规则式图表选择
- [x] 11.3 安全图表数据构造（report_period 不当 float）
- [x] 11.4 answer.py 单位感知格式化（从 schema 读字段单位）

## 12. Pipeline + Gradio

- [x] 12.1 pipeline.py --task etl
- [x] 12.2 pipeline.py --task answer --questions xlsx（多轮分组处理）
- [x] 12.3 app.py Gradio 界面（安全图表数据 + 无 ensure_demo_db）
- [x] 12.4 ETL 入库后可查询验证
