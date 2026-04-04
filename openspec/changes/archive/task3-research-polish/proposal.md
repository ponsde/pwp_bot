# 任务三答案质量优化

## 背景

task3-research-rag 已实现核心功能（RAG 检索、三路由、归因分析），端到端能跑通。但答案输出质量还有几个问题影响交作业评分。

## 问题清单

### P0 — 必须修

1. **references 的 paper_path 是 OV 内部 URI**
   - 当前：`内涵外延双轮驱动经营拐点已现_2.md`、`.overview.md`
   - 期望：`./附件5：研报数据/个股研报/2025年三季报点评：内涵+外延双轮驱动，经营拐点已现.pdf`
   - retriever.py 的 source 映射需要处理 OV 的 `viking://resources/...` URI 格式

2. **refs 的 text 是英文 VLM 摘要，不是中文原文**
   - 当前：ov_adapter.py search 用 `client.read(uri)` 读了完整 markdown，太长
   - 期望：截取命中段落的关键中文片段（200-500 字），不是整个文件

3. **B2003 Q1 答案重复**
   - 三年营收数据出现了两遍（6 行而不是 3 行）
   - 原因：SQL 路径的多意图拆分对单问题也做了处理，或 SQL 跑了两次

4. **答案包含技术性 warning**
   - 如"原始任务明确要求查询主营业务收入…指标不符合原始任务"
   - 这是 text2sql 的验证层反馈，不应暴露给最终用户

### P1 — 该做

5. **Hybrid 路径答案格式**
   - B2003 Q2 的答案前面不应有 SQL 查询结果的重复数据
   - hybrid 应只展示归因分析部分，SQL 数据在 Q1 已回答

6. **图表渲染确认**
   - B2003 Q1 的 chart_type=bar，但需要确认 result/ 下有对应 jpg 生成

## 不做

- 不改 text2sql 核心逻辑
- 不改 OV 索引策略
- 不改 ETL / 任务二代码
