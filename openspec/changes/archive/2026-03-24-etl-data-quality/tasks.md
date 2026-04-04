## 1. 跨页表格合并修复

- [x] 1.1 合并后追踪最末页码（last_merged_page），用于后续相邻判断
- [x] 1.2 允许间隔 1 页的合并（page_number - last_merged_page <= 2），因为跨页表可能跨 3+ 页
- [x] 1.3 验证：华润三九 2024HY balance_sheet 应包含负债合计和权益合计

## 2. balance_sheet 负债/权益覆盖率提升

- [x] 2.1 修复跨页合并后，重新检查覆盖率（29% → 75%）
- [x] 2.2 修复 section header 污染 pending_label（"流动资产：" 等段落标题被拼入下一行标签）
- [x] 2.3 修复空值行（"专项储备"等）污染 pending_label → 只有已知别名才累积

## 3. core_performance 年报/季报数据补全

- [x] 3.1 诊断 2022FY、2024FY 为什么 core_performance 全空 → 表头匹配 + 列对齐问题
- [x] 3.2 诊断 2025Q1、2025Q3 为什么全空 → 同上
- [x] 3.3 修复表分类（page text 检查 + body 确认关键词）和列头匹配（±2 偏移搜索）
- [ ] 3.4 目标：eps/roe 覆盖率 ≥ 90%（当前 50%/54%，需要更复杂的列头解析）

## 4. income_sheet 净利润缺失修复

- [x] 4.1 诊断 华润三九 2023Q3、金花股份 2024Q3 净利润为 None → 多行标签拆分问题
- [x] 4.2 Coder 修复多行标签拼接 + Leader 修复 Coder 引入的回归（header 拼入标签）
- [x] 4.3 operating_profit reconciliation：部分改善，非核心阻塞

## 5. 验证与回归

- [x] 5.1 重新跑 ETL，确认 24/24 loaded, 0 rejected ✓
- [ ] 5.2 四张表核心字段填充率统计 ≥ 90%（当前 income 94%, balance 82%, cashflow 98%, core 40%）
- [x] 5.3 heuristic 查询全部通过 ✓ (9/9 → 4/4 验证)
- [x] 5.4 单元测试全部通过 ✓ (14/14)

## Duel Debug 对抗赛修复

- [x] D1 移除错误的 eps 派生公式（万元×10000÷万元 = 放大1万倍）
- [x] D2 修复现金流占比公式（移除多余 ×10000）
- [x] D3 移除死代码（page_to_prev_record / _snapshot_numeric_records）
