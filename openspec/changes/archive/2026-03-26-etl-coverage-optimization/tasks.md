## 1. core_performance 派生字段

- [x] 1.1 在 `_compute_derived_fields` 中从 income_sheet 计算 gross_profit_margin
- [x] 1.2 在 `_compute_derived_fields` 中从 income_sheet 计算 net_profit_margin
- [x] 1.3 从 income_sheet 同步 total_operating_revenue 到 core_performance

## 2. core_performance 列头匹配改进

- [x] 2.1 诊断 net_asset_per_share 为什么匹配失败（多行标签被数字打断，移至 phase2）
- [x] 2.2 改进 2022FY、2024FY 年报的核心指标表列头解析（加了 alias、列头候选、normalize）
- [ ] 2.3 目标：eps/roe 从 50%/54% 提升到 80%+（roe 达 83%，eps 需 phase2 改 core 解析）

## 3. yoy/qoq 增长率计算

- [ ] 3.1 ETL 后处理：跨 period 计算 yoy 增长率（移至 phase2，需架构改造）
- [ ] 3.2 支持 FY/HY/Q1/Q3 对应上年同期匹配（移至 phase2）

## 4. balance_sheet 跨页补全

- [x] 4.1 诊断剩余 6 个 period 缺负债/权益的根因（续页被误分类为 income_sheet）
- [x] 4.2 改进跨页合并或增加二次扫描（加了续页 body 关键词检测 + 确认关键词）

## 5. income_sheet 边际改进

- [x] 5.1 修复 4 个 net_profit 为 None 的 period（修复了 2 个，剩余 2 个 Q3 移至 phase2）
- [x] 5.2 提升 taxes_and_surcharges / total_operating_expenses 覆盖率（均达 100%）
