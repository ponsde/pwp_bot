## 1. income/cashflow YoY 后处理

- [x] 1.1 在 loader.py 增加 _postprocess_income_growth_fields：计算 operating_revenue_yoy_growth、net_profit_yoy_growth
- [x] 1.2 在 loader.py 增加 _postprocess_cashflow_growth_fields：计算 net_cash_flow_yoy_growth
- [x] 1.3 补测试覆盖
- [x] 1.4 目标：三个字段 66%+ ✓ 实际 66.67%

## 2. roe_weighted_excl_non_recurring 提取/推导

- [x] 2.1 诊断为何 alias 存在但提取为 0%（根因：PDF 中跨行拆分，alias 未稳定命中）
- [x] 2.2 如提取不到，增加推导：net_profit_excl_non_recurring / equity * 100
- [x] 2.3 目标：60%+ ✓ 实际 83.33%

## 3. 数据正确性自检脚本

- [x] 3.1 新建 scripts/etl_quality_check.py
- [x] 3.2 检查项：值域合理性（eps ∈ [-50, 50]、revenue > 0 等）
- [x] 3.3 检查项：跨表一致性（core.revenue == income.revenue）
- [x] 3.4 检查项：YoY 计算验证（手算 vs DB 值比对）
- [x] 3.5 检查项：覆盖率汇总报告

## 4. QoQ 评估

- [x] 4.1 评估 QoQ 实现复杂度（Q4 = FY - Q3 问题）
- [x] 4.2 跳过：标准 QoQ 需季度单季值，Q4 需 FY-Q3 反推，错误风险高于收益

## 5. net_cash_flow 单位换算

- [x] 5.1 定位 net_cash_flow 提取时为何未做万元换算（根因：该字段走独立提取路径，未经 _convert_value 统一换算）
- [x] 5.2 修复：新增 _convert_statement_value 对 net_cash_flow 定向换算为万元
- [x] 5.3 验证：值域自检 0 issues ✓

## 6. Q3 跨表口径一致性

- [x] 6.1 确认 core 表 Q3 取的是"本报告期"（单季度），income 取的是累计
- [x] 6.2 修复：_compute_derived_fields 中 Q3 强制用 income 累计值覆盖 core.total_operating_revenue
- [x] 6.3 验证：跨表一致性自检 0 issues ✓

## 7. 净利润口径修正

- [x] 7.1 修复 _fill_income_sheet_from_page_text 优先匹配归母净利润（NET_PROFIT_PARENT_LABELS）
- [x] 7.2 补测试 ✓ 正则扩展支持冒号等分隔符

## 8. fallback 后处理包含当前期

- [x] 8.1 修改 _latest_non_null_balance_value 和 _latest_non_null_share_capital：< 改为 <=
- [x] 8.2 补测试 ✓ test_loader_postprocess_fallback_fields_uses_current_period_balance_and_share_capital
