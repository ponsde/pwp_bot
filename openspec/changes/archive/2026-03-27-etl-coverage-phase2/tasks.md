## 1. Core 多行标签解析改进

- [x] 1.1 改进 `_extract_core_metrics` 处理行标签被数字值打断的情况（如 "归属于上市" | 数字 → "公司股东的" → "净利润"）
- [x] 1.2 确保 EPS（"基本每股收益"）能从年报/季报的核心指标表中提取
- [x] 1.3 确保 net_asset_per_share 能正确提取
- [x] 1.4 确保 net_profit_excl_non_recurring 能从多行拆分标签中提取
- [x] 1.5 目标：eps/net_asset_per_share 从 0% 提升到 60%+

## 2. Q3 报告 net_profit 缺失

- [x] 2.1 诊断 600080 2024Q3 的 income_sheet.net_profit 为 None 的根因
- [x] 2.2 诊断 000999 2023Q3 的 income_sheet.net_profit 为 None 的根因
- [x] 2.3 修复提取逻辑（`_fill_income_sheet_from_page_text` 页面文本回退）

## 3. yoy/qoq 增长率后处理

- [x] 3.1 在 loader.py 或 pipeline 中增加 ETL 后处理步骤
- [x] 3.2 ETL 全量加载完后，查询 DB 计算 yoy = (本期-上期)/|上期| × 100
- [x] 3.3 支持 FY/HY/Q1/Q3 对应上年同期匹配
- [x] 3.4 目标：核心 yoy 字段从 0% 提升到 50%+

## 4. operating_cf_per_share 派生

- [x] 4.1 在 balance_sheet aliases 中增加"股本"→ share_capital 提取（含 Duel Debug 修复：增加 "实收资本" alias）
- [x] 4.2 在 _compute_derived_fields 中用 operating_cf_net_amount / share_capital 计算
