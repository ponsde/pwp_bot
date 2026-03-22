# AI-CONTEXT: 财报智能问答助手（泰迪杯）

## 项目简介

泰迪杯比赛项目，构建"财报智能问数助手"：用户用自然语言提问财务数据相关问题，系统通过 Text2SQL 查询 SQLite 返回精确答案，通过 RAG 检索年报原文回答分析型问题。创新点是集成 OpenViking 上下文记忆系统，赋予系统跨会话的用户偏好记忆和联想推荐能力。

## 技术栈

- **语言**: Python 3.10+
- **LLM**: gpt-5.4 via oai.whidsm.cn/v1（OpenAI 兼容协议）
- **Embedding**: BAAI/bge-m3 via 同源 endpoint
- **数据库**: SQLite（垂直表设计）
- **数据来源**: AKShare API（结构化财务数据）、PDF 年报（全文文本）
- **记忆系统**: OpenViking（embedded 模式）
- **UI**: Gradio
- **PDF 解析**: pdfplumber

## 目录结构

```
taidi_bei/
├── PLAN.md                    ← 项目总计划
├── AI-CONTEXT.md              ← 本文件（Agent 共享背景）
├── src/                       ← 源代码
│   ├── etl/                   ← 数据处理（api_fetcher, schema, loader, pdf_parser）
│   ├── query/                 ← 查询引擎（text2sql）
│   ├── llm/                   ← LLM 客户端封装
│   ├── viking/                ← OpenViking 集成
│   └── prompts/               ← Prompt 模板（.md 文件）
├── app.py                     ← Gradio 入口
├── config.py                  ← 配置管理
├── data/                      ← 数据（raw PDF, db, processed）
├── tests/                     ← 测试
├── openspec/                  ← OpenSpec 变更管理
└── references/                ← 参考项目（chatbot_financial_statement, FinGLM, OpenViking-examples）
```

## 架构概要

三引擎架构：Text2SQL（精确数值）、RAG（语义检索）、OpenViking（记忆+联想）。Orchestrator 负责意图分类和路由。Phase 1 只实现 Text2SQL + OV Resource 导入。

## 约定

- 不可变数据模式（创建新对象，不修改原对象）
- 文件 < 400 行，函数 < 50 行
- 环境变量存密钥，.env.example 文档化
- 垂直表设计（每行一个指标值）
- 两步式 Text2SQL（Step1 意图提取 → Step2 SQL 生成）

## 注意事项

- AKShare API 可能限流，需要缓存和退避策略
- SQLite 垂直表在大数据量下需要索引优化
- OV 的 add_resource 接受文件路径（非内存文本），可直接传 PDF
- gpt-5.4 的 JSON mode 支持需实测验证
