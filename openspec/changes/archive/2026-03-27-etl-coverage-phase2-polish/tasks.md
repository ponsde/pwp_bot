## 1. net_asset_per_share 提取修复

- [x] 1.1 Debug 真实 PDF（华润三九年报）的 core 表，定位 net_asset_per_share 提取失败原因
- [x] 1.2 修复提取逻辑（多行标签合并 _split_core_row_segments）
- [x] 1.3 增加 net_asset_per_share 推导（equity × 10000 / share_capital）
- [x] 1.4 目标：net_asset_per_share 从 0% 提升到 60%+（实际 100%）

## 2. loader 层 DB 回退补缺失字段

- [x] 2.1 诊断缺失报告和根因（roe 缺 equity，net_asset_per_share 缺 share_capital）
- [x] 2.2 在 loader.py 增加 _postprocess_fallback_fields：查 DB 同 stock_code 最近一期 equity_total_equity 回退 roe
- [x] 2.3 同上，查最近一期 share_capital 回退 net_asset_per_share
- [x] 2.4 补测试：验证回退逻辑在有/无历史数据时的行为
- [x] 2.5 目标：roe 100%, net_asset_per_share 100%

## 3. YoY 全量验证

- [x] 3.1 全量 ETL 后检查 yoy 字段覆盖率
- [x] 3.2 抽检 2-3 个报告的 yoy 计算正确性
- [x] 3.3 loader.py _postprocess_growth_fields 实现 core + balance YoY 计算

## 4. 母公司表过滤

- [x] 4.1 在 pdf_parser.py 中增加 _has_parent_company_marker 过滤逻辑
- [x] 4.2 修复 test_pdf_parser_confirmation_and_invalid_filter 测试
- [x] 4.3 在 _merge_cross_page_tables 中增加母公司续页检查
