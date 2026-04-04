# ETL 覆盖率优化（低优先级）

## 背景

etl-data-quality change 后，三大报表覆盖率优秀（income 94%, balance 82%, cashflow 98%），
但 core_performance 只有 40%，部分字段仍为 0%。这些不阻塞任务二，但完善后能提升整体数据质量。

## 待优化项

### 1. core_performance 派生字段
- `gross_profit_margin`：从 income_sheet 的 (营收-营业成本)/营收 计算
- `net_profit_margin`：从 income_sheet 的 净利润/营收 计算
- `total_operating_revenue` in core：与 income_sheet 的值同步

### 2. core_performance 列头匹配改进
- `net_asset_per_share`：PDF 中有但当前列头匹配失败
- eps/roe 在 2022FY、2024FY 等年报中提取失败 → 需要更灵活的列头对齐

### 3. yoy/qoq 增长率字段（全 0%）
- 需要跨 period 计算：(本期-上期)/|上期| × 100
- 在 `_compute_derived_fields` 中增加跨记录计算

### 4. balance_sheet 半年报/季报缺失
- liability_total_liabilities 75%（6 个 period 缺失）
- equity_total_equity 75%
- 根因：跨页合并仍有 gap，需要更宽的 near_page 策略或二次扫描

### 5. income_sheet 边际改进
- net_profit 83%（4 个 None）
- operating_expense_taxes_and_surcharges 21%
- total_operating_expenses 21%

## 非阻塞

这些都不影响任务二（NL2SQL）的核心功能。查询命中率已 100%，核心指标数据准确。
