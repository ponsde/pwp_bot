# ETL 通用 PDF 支持 — 茅台 & 平安银行端到端跑通

## 背景

PDF parser 已支持从文件名自动检测格式、从 PDF 内容提取 stock_code。解析阶段通了：
- 贵州茅台 600519：243 tables
- 平安银行 000001：66 tables

但尚未验证完整 ETL 链路（parse → extract → validate → load → quality check）。需要确保这两份非中药公司的年报能正确入库，验证通用性。

## 已知风险

1. **平安银行是银行业**，报表结构和一般制造业/消费业差异大（如"利息净收入"替代"营业收入"、特殊资产负债科目），可能导致表格分类或字段映射失败
2. **茅台是消费/白酒行业**，格式与中药公司较接近，预期问题较少
3. **table_extractor 的 alias 表**只覆盖了中药公司常见字段名，其他行业可能有不同表述
4. **validator 可能因缺少必填字段而 reject**

## 目标

1. 茅台 2023 年报完整入库，质量自检 0 issues
2. 平安银行 2023 年报能入库（允许覆盖率较低，但不能报错崩溃）
3. pipeline 对未知公司的 PDF graceful 处理（报错不中断其他文件）

## 范围

- `src/etl/table_extractor.py` — 可能需要扩展 alias / 表格分类逻辑
- `src/etl/validator.py` — 放宽未知公司的校验策略
- `src/etl/pdf_parser.py` — 微调（如有需要）
- `tests/` — 补充通用 PDF 测试

## 不做

- 不改官方 schema（四张表结构不变）
- 不追求银行业报表的完美覆盖率（那是另一个 change 的事）
- 不修改 NL2SQL / 问答逻辑
