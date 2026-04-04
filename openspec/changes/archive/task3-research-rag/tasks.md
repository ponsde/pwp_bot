## 1. OpenViking 适配层

- [x] 1.1 创建 `src/knowledge/__init__.py`
- [x] 1.2 创建 `src/knowledge/ov_adapter.py`：init_client / store_resource / search 三个函数
- [x] 1.3 编写 OV 配置（ov.conf 放项目根目录，ov.conf.example 提供模板）
- [x] 1.4 验证：init → store 一份测试文本 → search 能召回

## 2. 研报加载

- [x] 2.1 创建 `src/knowledge/research_loader.py`：扫描附件5目录，加载 PDF + 元数据
- [x] 2.2 用 OV add_resource 加载 3 份研报 PDF
- [x] 2.3 如果 OV 原生分块质量不够，fallback 到 pdfplumber 自己分块 + store
- [x] 2.4 验证：search("华润三九业绩") 能召回相关段落

## 3. 检索器

- [x] 3.1 创建 `src/knowledge/retriever.py`：search 封装 + 来源格式化（paper_path, text）
- [x] 3.2 支持 top_k 参数，返回带 score 的结果列表
- [x] 3.3 验证：对 B2002 "国家医保目录新增的中药产品" 能检索到相关内容

## 4. 研报问答编排

- [x] 4.1 创建 `src/knowledge/research_qa.py`
- [x] 4.2 实现意图分类：LLM 判断 sql/rag/hybrid（带 heuristic fallback）
- [x] 4.3 实现多意图拆分：一个问题 → 多个子问题（LLM + heuristic fallback）
- [x] 4.4 SQL 路径：复用现有 Text2SQLEngine
- [x] 4.5 RAG 路径：retriever → LLM 基于召回段落生成答案
- [x] 4.6 Hybrid 路径：先 SQL 取数据，再 RAG 找原因，合并答案
- [x] 4.7 归因输出：答案附带 references 列表

## 5. Pipeline 集成

- [x] 5.1 `pipeline.py` 增加 `--task research` 入口
- [x] 5.2 读取附件6格式问题，路由到 research_qa
- [x] 5.3 输出 result_3.xlsx（编号, 问题, SQL查询语句, 图形格式, 回答——回答含 references）
- [x] 5.4 端到端验证：附件6 三道题全部产出答案

## 6. 测试

- [x] 6.1 ov_adapter 单元测试（mock OV client）
- [x] 6.2 研报加载集成测试
- [x] 6.3 意图分类测试（sql/rag/hybrid 路由正确）
- [x] 6.4 端到端 pipeline 测试
- [x] 6.5 现有 pytest 不退化
