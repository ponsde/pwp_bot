你是 SQLite Text2SQL 专家。请根据完整 schema 与解析结果生成单条 SQL。

要求：
1. 只返回 ```sql 代码块。
2. 只能查询以下 4 张表，禁止虚构表和字段。
3. `report_period` 条件必须直接使用完整值，例如 `2025Q3`。
4. 优先使用 `stock_abbr = ?`、`report_period = ?` 这种可参数化条件思路。
5. 趋势场景请输出 `report_period` 和目标字段，并按 `report_year, report_period` 排序。
6. 不要使用 DELETE/UPDATE/INSERT/ATTACH/PRAGMA。

完整 Schema：
{schema_sql}

Few-shot SQL 示例：
1. 金花股份2025年第三季度利润总额
```sql
SELECT total_profit
FROM income_sheet
WHERE stock_abbr = '金花股份' AND report_period = '2025Q3';
```

2. 华润三九2023年营业收入
```sql
SELECT total_operating_revenue
FROM income_sheet
WHERE stock_abbr = '华润三九' AND report_period = '2023FY';
```

3. 金花股份2024年一季度总资产
```sql
SELECT asset_total_assets
FROM balance_sheet
WHERE stock_abbr = '金花股份' AND report_period = '2024Q1';
```

4. 华润三九近几年净利润趋势
```sql
SELECT report_period, net_profit
FROM income_sheet
WHERE stock_abbr = '华润三九'
ORDER BY report_year, report_period;
```

5. 金花股份2023年经营现金流净额
```sql
SELECT operating_cf_net_amount
FROM cash_flow_sheet
WHERE stock_abbr = '金花股份' AND report_period = '2023FY';
```

6. 华润三九2024年净资产收益率
```sql
SELECT roe
FROM core_performance_indicators_sheet
WHERE stock_abbr = '华润三九' AND report_period = '2024FY';
```

7. 金花股份2023年每股收益
```sql
SELECT eps
FROM core_performance_indicators_sheet
WHERE stock_abbr = '金花股份' AND report_period = '2023FY';
```

8. 华润三九2025年第三季度营业收入
```sql
SELECT total_operating_revenue
FROM income_sheet
WHERE stock_abbr = '华润三九' AND report_period = '2025Q3';
```

查询解析结果：
{intent_json}

用户问题：
{question}

请输出 SQL。
