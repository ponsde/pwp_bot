# ETL Phase 2 收尾 — YoY 补全 + 数据质量自检 + 准确率修复

## 背景

Phase 2 核心字段 100%，YoY/roe 已补全（第一轮完成），质量自检脚本已建。
但自检暴露了 4 个准确率问题，4.25 新数据测试前必须修复。

## 已完成（第一轮）

- [x] income/cashflow YoY 后处理（66.67%，理论上限）
- [x] roe_weighted_excl_non_recurring 推导（83.33%）
- [x] 数据正确性自检脚本
- [x] QoQ 评估（跳过，复杂度过高）

## 待修复（第二轮）— 准确率问题

### 5. net_cash_flow 单位未换算

- `net_cash_flow` 存储为元，其他字段为万元，差 10000 倍
- 证据：`operating_cf_net_amount = 419,174`（万元）vs `net_cash_flow = 3,853,676,935`（元）
- 根因：table_extractor 提取 net_cash_flow 时未做单位换算
- 修复：在提取或后处理阶段统一为万元

### 6. Q3 跨表口径不一致

- core 表 Q3 revenue 是单季度值（本报告期），income 表是累计值（年初至报告期末）
- 证据：000999 Q3 core=546,188 vs income=1,860,800（约 3.4 倍）
- 根因：core 指标表取的是"本报告期"列，而 income 取的是累计列
- 修复：core 表 Q3 应取累计值，或在 _compute_derived_fields 中用 income 累计值回填

### 7. 净利润口径混淆（归母 vs 总）

- income_sheet.net_profit 在页面回填时可能匹配到"净利润"（总净利润）而非"归属于母公司股东的净利润"（归母净利润）
- 影响：下游问答和跨表一致性都会受影响
- 修复：`_fill_income_sheet_from_page_text` 优先匹配归母净利润

### 8. fallback 后处理排除当前期数据

- `_latest_non_null_balance_value` SQL 排除当前期（`< current_order`）
- 导致同一报告中 balance 已有数据但无法补到 core 的 roe/每股净资产
- 修复：改为 `<= current_order`（包含当前期）

## 范围

- `src/etl/table_extractor.py` — 单位换算、净利润口径、Q3 口径
- `src/etl/loader.py` — fallback 后处理包含当前期
- `scripts/etl_quality_check.py` — 调整 net_cash_flow 值域范围
- `tests/` — 补充相关测试

## 验收标准

- `PYTHONPATH=. python3 scripts/etl_quality_check.py data/db/finance.db` 输出 **0 issues**
- 所有测试通过
