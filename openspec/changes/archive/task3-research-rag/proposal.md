# 任务三：研报 RAG + 归因分析

## 背景

任务一（ETL）和任务二（NL2SQL）已完成。任务三要求基于研报数据回答复杂问题，包括：
- **多意图**：一个问题包含多个子问题（B2001）
- **意图模糊**：问题超出财报数据范围，需从研报检索（B2002）
- **归因分析**：结合财报数据 + 研报内容，给出带来源引用的答案（B2003）

数据来源：
- 附件5：3 份研报 PDF（2 份个股 + 1 份行业）+ 元数据 Excel
- 附件6：3 道示例题

输出：result_3.xlsx，答案需附带 references（paper_path, text, paper_image）

## 技术方案

### OpenViking 集成（模块化设计）

用 OpenViking v0.2.13 作为向量知识库，但**只通过薄适配层耦合**：

```
ov_adapter.py（~50行，唯一碰 OV 的文件）
  ├── init_client(data_path, config_path) → SyncOpenViking
  ├── store_resource(client, pdf_path) → uri
  └── search(client, query, top_k) → [{text, source, score}]
```

OV 更新时只改 `ov_adapter.py`，其余代码零影响。

### 问题路由

```
问题 → LLM 意图分类 →
  ├── "sql"    → 现有 text2sql（任务二）
  ├── "rag"    → OpenViking 检索 → LLM 生成答案
  └── "hybrid" → text2sql + OpenViking → LLM 合并答案
```

### 归因格式

```json
{
  "Q": "主营业务收入上升的原因是什么",
  "A": "根据西南证券研报...",
  "references": [
    {
      "paper_path": "./附件5：研报数据/个股研报/2025年三季报点评.pdf",
      "text": "公司CHC业务收入同比增长...",
      "paper_image": ""
    }
  ]
}
```

## 模块设计

| 文件 | 职责 | 依赖 |
|------|------|------|
| `src/knowledge/ov_adapter.py` | OV 薄适配层 | openviking |
| `src/knowledge/research_loader.py` | 研报 PDF 加载到 OV | ov_adapter |
| `src/knowledge/retriever.py` | 语义检索 + 来源追踪 | ov_adapter |
| `src/knowledge/research_qa.py` | 路由 + 编排 + 答案生成 + 归因 | retriever, text2sql, llm_client |
| `pipeline.py` 修改 | 增加 `--task research` 入口 | research_qa |

## 目标

1. `ov_adapter.py` 可独立测试（init → store → search 闭环）
2. 3 份示例研报成功加载到 OV
3. B2001（多意图）：拆分子问题，逐个 SQL 查询，合并答案
4. B2002（意图模糊）：OV 检索命中相关研报段落，生成答案
5. B2003（归因分析）：第一轮 SQL+图表，第二轮 RAG 找原因 + references
6. `pipeline.py --task research` 端到端产出 result_3.xlsx
7. OV 适配层模块化，OV 升级只需改 `ov_adapter.py`

## 不做

- 不改任务一/任务二已有代码的核心逻辑
- 不做研报图片提取（paper_image 暂为空字符串，后续可扩展）
- 不做 OV 深度定制（用标准 API：add_resource + search）

## 风险

1. OV add_resource 对中文 PDF 的分块质量未知——需实测后可能要自己分块再 store
2. OV search 的召回率——如果语义匹配不够好，可能需要关键词 + 语义混合检索
3. .venv 依赖管理——openviking 装在 .venv 里，需确保 pipeline 用对 Python
