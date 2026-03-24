## 1. 跨页表格合并修复

- [ ] 1.1 合并后追踪最末页码（last_merged_page），用于后续相邻判断
- [ ] 1.2 允许间隔 1 页的合并（page_number - last_merged_page <= 2），因为跨页表可能跨 3+ 页
- [ ] 1.3 验证：华润三九 2024HY balance_sheet 应包含负债合计和权益合计

## 2. balance_sheet 负债/权益覆盖率提升

- [ ] 2.1 修复跨页合并后，重新检查覆盖率（预计从 29% 大幅提升）
- [ ] 2.2 如有遗漏，补充 BALANCE_ALIASES（负债合计、权益合计的变体写法）

## 3. core_performance 年报/季报数据补全

- [ ] 3.1 诊断 2022FY、2024FY 为什么 core_performance 全空
- [ ] 3.2 诊断 2025Q1、2025Q3 为什么全空
- [ ] 3.3 修复表分类或列头匹配逻辑
- [ ] 3.4 目标：eps/roe 覆盖率 ≥ 90%

## 4. income_sheet 净利润缺失修复

- [ ] 4.1 诊断 华润三九 2023Q3、金花股份 2024Q3 净利润为 None
- [ ] 4.2 修复提取逻辑
- [ ] 4.3 检查 operating_profit reconciliation 差异是否减小

## 5. 验证与回归

- [ ] 5.1 重新跑 ETL，确认 24/24 loaded, 0 rejected
- [ ] 5.2 四张表核心字段填充率统计 ≥ 90%
- [ ] 5.3 heuristic 查询全部通过
- [ ] 5.4 单元测试全部通过
