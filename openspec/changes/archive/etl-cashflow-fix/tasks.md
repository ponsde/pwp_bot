## 1. 排查

- [ ] 1.1 用 pdfplumber 检查 600080_20240427_0WKP.pdf 中现金流量表的实际位置和结构
- [ ] 1.2 确认 table_extractor.py 的现金流量表标题匹配模式是否覆盖该 PDF 格式

## 2. 修复

- [ ] 2.1 修复分类逻辑，使现金流量表被正确识别
- [ ] 2.2 确保修复不破坏深交所 PDF（华润三九）的解析

## 3. 验证

- [ ] 3.1 test_pdf_parser_confirmation_and_invalid_filter 通过
- [ ] 3.2 其他 ETL 测试不退化
