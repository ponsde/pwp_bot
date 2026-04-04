## 1. LLM 接口适配（P0 阻塞）

- [x] 1.1 在 `LLMClient` 上添加 `complete(prompt: str, **kwargs) -> str` 便捷方法，内部包装为 `[{"role": "user", "content": prompt}]` 调 `chat_completion`
- [x] 1.2 确认 text2sql.py 5 处 `self.llm_client.complete(prompt)` 调用均兼容（analyze, generate_sql, validate_result, reflect, clarify）
- [x] 1.3 对 validate_result / reflect 场景，考虑传 `json_mode=True` 让 LLM 直接返回结构化 JSON（避免 `_parse_json` 二次提取失败）
- [x] 1.4 冒烟测试：单个问题 LLM 模式端到端跑通

## 2. Pipeline LLM 初始化（P0.5）

- [x] 2.1 `pipeline.py` `run_answer()` 中用 `LLMClient.from_env()` 创建客户端并传入 `Text2SQLEngine`
- [x] 2.2 无 API key 时的行为：尝试创建 client，失败则 warning + 降级 heuristic（保持现有兜底能力）
- [x] 2.3 LLM 调用超时/网络错误时：`chat_completion` 已有重试，但 pipeline 层需 catch 未恢复的异常，写入该题的 error 而非中断整批

## 3. Prompt 模板调优

- [x] 3.1 用 LLM 测试 seek_table.md 意图解析输出格式
- [x] 3.2 用 LLM 测试 generate_sql.md SQL 生成质量
- [x] 3.3 用 LLM 测试 validate_result.md / reflect.md 恢复机制
- [x] 3.4 修复 prompt 中格式/指令不清晰的地方

## 4. 防护：大结果集截断

- [x] 4.1 validate_result / reflect 传给 prompt 的 rows 做截断（如 ≤50 行），避免超长 prompt
- [x] 4.2 截断时在 prompt 中说明"结果已截断，共 N 行"

## 5. 端到端问答验证

- [x] 5.1 准备 10+ 测试问题（单值查询、比较、趋势、跨表、多轮对话）
- [x] 5.2 用 LLM 模式逐个跑，记录准确率
- [x] 5.3 修复失败 case
- [x] 5.4 目标：LLM 模式准确率 ≥ 80%（准确 = SQL 执行成功且回答内容与预期一致）

## 6. Answer Pipeline

- [x] 6.1 验证 pipeline.py --task answer 完整流程
- [x] 6.2 输出 result_2.xlsx 格式正确（编号、问题、SQL、图形格式、回答）
- [x] 6.3 图表生成正常

## 7. 回归

- [x] 7.1 heuristic 模式测试不受影响（`llm_client=None` 路径不动）
- [x] 7.2 `python3 -m pytest tests/ -v` 全部通过
