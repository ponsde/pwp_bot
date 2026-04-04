# ETL 覆盖率收尾打磨

## 背景

Phase 2 完成后四张表核心字段基本 100%，但仍有少量遗漏和可提升项。

## 待优化项

### 1. net_asset_per_share 仍为 0%（core）

- alias 存在（"归属于上市公司股东的每股净资产"、"每股净资产"），单元测试通过
- 但 24 份实际 PDF 中无一提取成功，需 debug 真实 PDF 的 core 表定位原因
- 可能原因：年报中该标签跨行拆分，或列头匹配选错值

### 2. loader 层 DB 回退补缺失字段

已确认缺失根因：部分 Q1/Q3 季报的 balance_sheet 缺 share_capital 或 equity_total_equity，导致推导字段缺失。

需在 loader.py 的后处理阶段查 DB 中同 stock_code 最近一期有值的记录做回退：
- **roe**: 缺 2 条（金花股份 2023Q1、2025Q3），根因是缺 equity_total_equity
- **net_asset_per_share**: 缺 4 条，根因是缺 share_capital
- 实现方式：`_postprocess_fallback_fields(conn)` 在 `_postprocess_growth_fields` 之前调用

### 3. YoY 增长率全量验证

- 后处理逻辑已实现，但 coverage 脚本只跑了 extractor.extract() 没经过 DB
- 需全量 ETL 后检查 yoy 字段的实际覆盖率和正确性
- 确认 FY/HY/Q1/Q3 各期同比均正确

### 4. Phase 1 遗留 parser bug

- `test_pdf_parser_confirmation_and_invalid_filter` 失败
- "母公司"报表被误分类为 balance_sheet/income_sheet/cash_flow_sheet
- 需在 pdf_parser.py 中增加"母公司"表的过滤逻辑

## 范围

- `src/etl/table_extractor.py` — net_asset_per_share 提取修复
- `src/etl/loader.py` — roe 回退逻辑（可选）
- `src/etl/pdf_parser.py` — 母公司表过滤
- `tests/test_etl_phase1.py` — 补充断言
