## 1. 比较类回答保留公司名（P1）

- [x] 1.1 修改 `build_answer_content()` 多行分支：当结果包含 `stock_abbr` 列时，用公司名作为行前缀
- [x] 1.2 示例格式：`金花股份：营业收入=5.65亿元` 而非 `total_operating_revenue=5.65亿元`
- [x] 1.3 同时把 `report_period` 也作为有意义的行标识保留（趋势场景需要）
- [x] 1.4 补测试

## 2. 单值查询不出图（P1）

- [x] 2.1 在 `select_chart_type()` 开头加判断：`if len(rows) <= 1: return "none"`
- [x] 2.2 补测试

## 3. 计算类 SQL 支持（P2）

- [x] 3.1 在 `generate_sql.md` 中增加计算类 few-shot 示例（比率、差值、同比）
- [x] 3.2 在 `seek_table.md` 中增加计算类意图示例（fields 包含多个字段用于计算）
- [x] 3.3 用 LLM 实测计算类问题验证效果
- [x] 3.4 补测试

## 4. 回归

- [x] 4.1 已有 16 个测试全部通过（22 个全通过）
- [x] 4.2 重跑 10 题实测验证改进效果
