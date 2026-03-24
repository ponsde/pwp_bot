# ETL 数据质量加固

## 问题

当前 ETL 提取出的数据存在以下质量问题：

### 1. balance_sheet 负债/权益覆盖率低
- 半年报和季报中 `liability_total_liabilities` 和 `equity_total_equity` 大量为 NULL
- 12 个华润三九 period 中只有 5 个有完整的负债+权益数据
- 原因：半年报/季报的合并资产负债表结构不同，负债合计/权益合计在跨页部分未被提取

### 2. core_performance 年报数据缺失
- 2022FY、2024FY 的 eps/roe/净利润全为 NULL
- 2025Q1、2025Q3 也全为 NULL
- 原因：年报核心指标表的列头格式多样，匹配失败

### 3. income_sheet operating_profit 勾稽差异大
- 多个 period 的 operating_profit reconciliation warning
- 金花股份尤其严重（expected vs actual 差数倍）
- 原因：营业成本/营业总成本字段未正确提取，或提取了非合并数据

### 4. 部分 period 净利润为 None
- 2023Q3 净利润 None
- 原因：季报利润表结构中净利润行位置不同

## 目标

- 四张表核心字段填充率 ≥ 90%
- balance_sheet 负债+权益覆盖率从 42% 提升到 80%+
- core_performance eps/roe 覆盖率从 79% 提升到 90%+
- operating_profit reconciliation 差异降低

## 范围

- `src/etl/pdf_parser.py` — 表分类改进
- `src/etl/table_extractor.py` — 字段提取、跨页处理、别名补全
- `src/etl/validator.py` — 可能调整容差
- `tests/test_etl_phase1.py` — 更新/新增覆盖率测试
