## 1. 报表列选择优化

- [x] 1.1 `_extract_statement_table` 增加表头解析：识别"期末余额/期末数"和"期初余额/期初数"列索引
- [x] 1.2 有表头时按列索引取值，无表头时 fallback 到现有 `_find_first_numeric`（保持兼容）
- [x] 1.3 删除 `_find_first_numeric` 中的 "小整数跳过" 临时补丁（被表头方案取代）
- [x] 1.4 验证：茅台 share_capital 提取正确（125,619.78 万元级别），per-share 指标合理

## 2. 表格分类收紧

- [x] 2.1 `_classify_table` 增加排除关键词：含"股东权益变动""所有者权益变动"的表不标为 income/balance/cashflow
- [x] 2.2 增加最小行数门槛：少于 3 行数据的表不分类（排除残片）
- [x] 2.3 验证：茅台 page 63 残片不再被误分类为 income_sheet

## 3. 银行业 alias 扩展

- [x] 3.1 利润表：手续费及佣金净收入、信用减值损失、其他业务收入、营业支出等
- [x] 3.2 现金流量表：客户存款和同业存放款项净增加额、向中央银行借款净增加额等（映射到最接近的 schema 字段）
- [x] 3.3 资产负债表：发放贷款及垫款→应收账款、拆出资金等
- [x] 3.4 core 指标表：补充银行 EPS 表述（每股收益/基本每股收益）
- [x] 3.5 验证：平安银行 income ≥ 4 fields, cashflow ≥ 3 fields, balance ≥ 6 fields

## 4. 回归测试

- [x] 4.1 华润三九 2022FY core ≥ 10/15（不退化）
- [x] 4.2 金花股份 2022FY core ≥ 10/15（不退化）
- [x] 4.3 茅台 2023FY 核心指标全部正确（eps, revenue, profit, roe, net_asset_per_share）
- [x] 4.4 平安银行 2023FY 不崩溃，覆盖率提升
- [x] 4.5 全量 pytest 通过
