# ETL 覆盖率优化 Phase 2

## 背景

Phase 1 完成后，三大报表覆盖率优秀（income 82%, balance 78%, cash_flow 90%），
core_performance 从原来的 ~40% 提升到 31%（行数从 17 增到 24）。
主要提升来自派生字段（毛利率/净利率 100%）和 balance 修复（liability/equity 100%）。

但以下字段仍为 0% 或很低，需要继续优化。

## 待优化项

### 1. EPS / 每股净资产提取（core 0%）

- 年报"主要会计数据和财务指标"表已能识别为 core（加了 `营业收入` token），但 core 提取逻辑（`_extract_core_metrics`）无法正确处理多行标签拆分+中间夹数字值的情况
- 例：`"基本每股收"` (row 22) + `"益（元/股）"` (row 23)，值 `2.63` 在 row 22 中
- 季报格式不同：通常是简单的 key-value 行，但也有列头对齐问题
- 目标：eps 从 0% 提升到 60%+，net_asset_per_share 从 0% 到 60%+

### 2. net_profit 缺失 2 个 Q3 报告

- 600080 2024Q3 和 000999 2023Q3 的 income_sheet.net_profit 为 None
- 需诊断根因（可能是列头匹配失败或跨页提取问题）

### 3. yoy/qoq 增长率计算（架构改造）

- 当前 `TableExtractor.extract()` 是单报告处理，无法做跨 period 计算
- 需要在 `loader.py` 或 pipeline 层面增加后处理步骤
- 在 ETL 全部加载完后，查询 DB 中的历史数据计算同比/环比
- 目标：yoy 字段从 0% 提升到 50%+

### 4. operating_cf_per_share（core 0%）

- Phase 1 移除了错误 alias，但正确 alias（`"每股经营现金流量"`）在 PDF 核心指标表中很少出现
- 可能需要从 cash_flow_sheet 的 `operating_cf_net_amount` 和股本数计算
- 股本数可从 balance_sheet 的"股本"字段获取（当前未提取）

### 5. net_profit_excl_non_recurring（core 0%）

- 扣非净利润在年报表中有（"归属于上市公司股东的扣除非经常性损益的净利润"），但多行标签打断导致匹配失败
- 与 EPS 问题同根（core 多行标签解析）
