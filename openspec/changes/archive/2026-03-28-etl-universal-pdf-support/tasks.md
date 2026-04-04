## 1. 茅台端到端入库验证

- [x] 1.1 跑 pipeline ETL 入库茅台年报，检查入库结果
- [x] 1.2 诊断 core 只有 7 fields 的原因（中药公司通常 14+），补充缺失字段的提取
- [x] 1.3 跑质量自检，修复 issues 直到 0
- [x] 1.4 目标：核心字段（eps, revenue, profit, roe）全部非空

## 2. 平安银行 graceful 处理

- [x] 2.1 诊断为何 income 只有 1 field、cash_flow 为 0（银行业格式差异）
- [x] 2.2 确保 pipeline 不因字段缺失而崩溃（validator 不 reject 未知公司）
- [x] 2.3 能入库多少就入库多少，不强求覆盖率

## 3. pipeline 健壮性

- [x] 3.1 pipeline 跑通 reports-通用测试 目录，错误不中断其他文件
- [x] 3.2 pipeline 日志输出每个文件的处理结果（loaded/skipped/error + 原因）
- [x] 3.3 补测试
