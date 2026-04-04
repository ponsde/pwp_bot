## 1. QueryResult 增加 warning 字段（P1）

- [x] 1.1 `QueryResult` dataclass 增加 `warning: str | None = None`
- [x] 1.2 `_query_with_recovery` 中验证/反思重试失败时，如果 rows 非空，返回结果 + warning（reason 作为 warning 内容），而非抛 `UserFacingError`
- [x] 1.3 只有 rows 为空时才抛 `UserFacingError`
- [x] 1.4 补测试：验证失败但有数据 → 返回 warning 而非 error

## 2. pipeline 传递 warning 到 answer（P1）

- [x] 2.1 `pipeline.py` 中 `result.warning` 非空时，在 content 末尾追加 `\n（注：{warning}）`
- [x] 2.2 有 warning 的结果仍然走正常的 chart 路径（不进 error 分支）
- [x] 2.3 补测试

## 3. select_chart_type 增加可视化关键词（P2）

- [x] 3.1 增加"绘图"、"可视化"、"画图"、"图表"关键词检测 → 多行时默认 bar
- [x] 3.2 补测试

## 4. 回归

- [x] 4.1 已有 20 个测试全部通过
- [x] 4.2 重跑附件4+附件6实测验证降级效果
