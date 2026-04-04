# 任务二：NL2SQL 智能问答端到端

## 目标

让 Text2SQL 引擎在 LLM 模式下真正可用：用户提问 → LLM 解析意图 → 生成 SQL → 执行 → 格式化回答 + 图表 → 输出到 result_2.xlsx。

## 当前问题

### P0: 接口不匹配（LLM 模式完全不能工作）
- `text2sql.py` 调用 `self.llm_client.complete(prompt)` — 传入单个字符串
- `LLMClient.chat_completion()` 期望 `messages: list[dict]` — OpenAI chat format
- LLM 模式下 analyze/generate_sql/validate_result/reflect/clarify **五处**调用都会报 AttributeError

### P0.5: pipeline.py 未初始化 LLM 客户端
- `run_answer()` 中 `Text2SQLEngine(db_path=db_path)` 未传 `llm_client`
- 即使修复了接口，answer pipeline 仍然只走 heuristic 模式
- 需要 `LLMClient.from_env()` 并传入 engine

### P1: Prompt 模板质量未经 LLM 验证
- `seek_table.md`、`generate_sql.md` 等模板是为 heuristic 写的 few-shot，未用真实 LLM 测过
- JSON 输出格式可能不被 LLM 正确遵循
- 需要用真实问题验证并调优

### P2: answer pipeline 端到端
- `pipeline.py --task answer` 需要读 questions xlsx → 分组多轮 → 查询 → 图表 → 写 result_2.xlsx
- 需要用示例问题集验证完整流程

## 范围

- `src/llm/client.py` — 增加 `complete(prompt)` 便捷方法（包装 chat_completion）
- `src/query/text2sql.py` — 5 处 LLM 调用适配；对 validate/reflect 场景考虑用 `json_mode=True`
- `src/prompts/*.md` — 调优 prompt 模板
- `pipeline.py` — 初始化 LLMClient 并传入 engine；验证 answer 流程
- 端到端测试：用 10+ 真实问题验证准确率
- **防护**：validate/reflect prompt 中的 rows 需截断（防大结果集撑爆 prompt）

## 不含

- 任务三（RAG）
- ETL 覆盖率优化（已有单独 change）
- `answer.md` 模板的 LLM 驱动回答生成（当前 `build_answer_content` 用规则即可）
- `chart_select.md` 的 LLM 驱动图表选择（当前规则引擎足够）
