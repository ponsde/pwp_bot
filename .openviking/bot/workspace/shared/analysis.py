import pandas as pd
import numpy as np

# 原始数据
data = [
    ("000423", "东阿阿胶", "2023Q3", 342828.25, 8562.69),
    ("000423", "东阿阿胶", "2024Q3", 432922.92, 8946.72),
    ("000423", "东阿阿胶", "2025Q3", 476637.06, 14519.6),
    ("000538", "云南白药", "2023Q3", 2968853.21, 21860.6),
    ("000538", "云南白药", "2024Q3", 2991515.51, 21618.26),
    ("000538", "云南白药", "2025Q3", 3065421.42, 23499.82),
    ("000590", "启迪药业", "2023Q3", 27462.98, 925.29),
    ("000590", "启迪药业", "2024Q3", 21623.12, 972.52),
    ("000590", "启迪药业", "2025Q3", 22481.58, 1166.31),
    ("000650", "仁和药业", "2023Q3", 381869.19, 2941.27),
    ("000650", "仁和药业", "2024Q3", 315063.77, 2320.15),
    ("000650", "仁和药业", "2025Q3", 283345.18, 2640.3),
    ("000766", "通化金马", "2023Q3", 104424.21, 2974.07),
    ("000766", "通化金马", "2024Q3", 96858.92, 2849.96),
    ("000766", "通化金马", "2025Q3", 89225.11, 2799.16),
    ("000790", "华神科技", "2023Q3", 67245.55, 1269.55),
    ("000790", "华神科技", "2024Q3", 66307.92, 1057.76),
    ("000790", "华神科技", "2025Q3", 45738.46, 1037.36),
    ("000989", "九芝堂", "2023Q3", 237023.18, 9124.12),
    ("000989", "九芝堂", "2025Q3", 162745.33, 9373.57),
    ("000999", "华润三九", "2023Q3", 1860800.6, 45844.32),
    ("000999", "华润三九", "2024Q3", 1974028.7, 51218.2),
    ("000999", "华润三九", "2025Q3", 2198640.4, 84033.3),
    ("002082", "万邦德", "2023Q3", 101790.95, 3890.43),
    ("002082", "万邦德", "2024Q3", 107449.11, 4225.86),
    ("002082", "万邦德", "2025Q3", 101770.64, 4926.6),
    ("002107", "沃华医药", "2023Q3", 71639.24, 3652.34),
    ("002107", "沃华医药", "2024Q3", 57667.87, 2938.34),
    ("002107", "沃华医药", "2025Q3", 62461.34, 2722.35),
    ("002166", "莱茵生物", "2023Q3", 88897.74, 3489.45),
    ("002166", "莱茵生物", "2024Q3", 116996.51, 4736.39),
    ("002166", "莱茵生物", "2025Q3", 127215.58, 5041.59),
    ("002198", "嘉应制药", "2023Q3", 37723.14, 673.95),
    ("002198", "嘉应制药", "2024Q3", 25960.46, 558.37),
    ("002198", "嘉应制药", "2025Q3", 29343.63, 716.77),
    ("002219", "新里程", "2023Q3", 250707.45, 690.57),
    ("002219", "新里程", "2024Q3", 268074.84, 751.43),
    ("002219", "新里程", "2025Q3", 225609.55, 1214.98),
    ("002275", "桂林三金", "2023Q3", 163176.82, 10533.34),
    ("002275", "桂林三金", "2024Q3", 157478.76, 11485.12),
    ("002275", "桂林三金", "2025Q3", 146238.21, 9105.48),
    ("002287", "奇正藏药", "2023Q3", 124623.68, 4013.38),
    ("002287", "奇正藏药", "2024Q3", 147175.48, 4177.38),
    ("002287", "奇正藏药", "2025Q3", 152294.38, 4965.12),
    ("002317", "众生药业", "2023Q3", 207127.86, 8111.93),
    ("002317", "众生药业", "2024Q3", 190802.2, 8609.14),
    ("002317", "众生药业", "2025Q3", 188875.39, 5991.99),
    ("002349", "精华制药", "2023Q3", 111965.92, 4454.46),
    ("002349", "精华制药", "2024Q3", 104517.23, 4715.0),
    ("002349", "精华制药", "2025Q3", 109228.54, 4353.66),
]

df = pd.DataFrame(data, columns=['stock_code', 'stock_abbr', 'report_period', 'total_operating_revenue', 'operating_expense_rnd_expenses'])

# 按公司分组分析
print("=" * 80)
print("①【连续增长公司识别】")
print("=" * 80)

growing_companies = []

for code in df['stock_code'].unique():
    company_data = df[df['stock_code'] == code].sort_values('report_period')
    
    # 检查是否有2023Q3、2024Q3、2025Q3三个数据点
    periods = company_data['report_period'].tolist()
    
    if len(company_data) >= 3 and '2023Q3' in periods and '2024Q3' in periods and '2025Q3' in periods:
        abbr = company_data['stock_abbr'].iloc[0]
        
        # 获取三个报告期的数据
        data_2023q3 = company_data[company_data['report_period'] == '2023Q3'].iloc[0]
        data_2024q3 = company_data[company_data['report_period'] == '2024Q3'].iloc[0]
        data_2025q3 = company_data[company_data['report_period'] == '2025Q3'].iloc[0]
        
        rev_2023q3 = data_2023q3['total_operating_revenue']
        rev_2024q3 = data_2024q3['total_operating_revenue']
        rev_2025q3 = data_2025q3['total_operating_revenue']
        
        # 检查是否连续增长
        growth_2023_2024 = rev_2024q3 > rev_2023q3
        growth_2024_2025 = rev_2025q3 > rev_2024q3
        
        if growth_2023_2024 and growth_2024_2025:
            growing_companies.append({
                'stock_code': code,
                'stock_abbr': abbr,
                'rev_2023q3': rev_2023q3,
                'rev_2024q3': rev_2024q3,
                'rev_2025q3': rev_2025q3,
                'rnd_2023q3': data_2023q3['operating_expense_rnd_expenses'],
                'rnd_2024q3': data_2024q3['operating_expense_rnd_expenses'],
                'rnd_2025q3': data_2025q3['operating_expense_rnd_expenses'],
            })
            
            print(f"\n✓ {code} - {abbr}")
            print(f"  2023Q3: {rev_2023q3:,.2f}万元")
            print(f"  2024Q3: {rev_2024q3:,.2f}万元 (增长 {((rev_2024q3/rev_2023q3-1)*100):.2f}%)")
            print(f"  2025Q3: {rev_2025q3:,.2f}万元 (增长 {((rev_2025q3/rev_2024q3-1)*100):.2f}%)")

print(f"\n共找到 {len(growing_companies)} 家连续增长公司")

# ②计算CAGR
print("\n" + "=" * 80)
print("②【复合年增长率(CAGR)计算】")
print("=" * 80)

cagr_list = []
for company in growing_companies:
    # CAGR = (末期值/初期值)^(1/年数) - 1
    # 从2023Q3到2025Q3是2年
    cagr = ((company['rev_2025q3'] / company['rev_2023q3']) ** (1/2) - 1) * 100
    company['cagr'] = cagr
    cagr_list.append(cagr)
    
    print(f"\n{company['stock_code']} - {company['stock_abbr']}")
    print(f"  CAGR (2023Q3-2025Q3): {cagr:.2f}%")

avg_cagr = np.mean(cagr_list)
print(f"\n平均CAGR: {avg_cagr:.2f}%")

# ③研发投入累计金额
print("\n" + "=" * 80)
print("③【研发投入累计金额】")
print("=" * 80)

for company in growing_companies:
    total_rnd = company['rnd_2023q3'] + company['rnd_2024q3'] + company['rnd_2025q3']
    company['total_rnd'] = total_rnd
    
    print(f"\n{company['stock_code']} - {company['stock_abbr']}")
    print(f"  2023Q3研发: {company['rnd_2023q3']:,.2f}万元")
    print(f"  2024Q3研发: {company['rnd_2024q3']:,.2f}万元")
    print(f"  2025Q3研发: {company['rnd_2025q3']:,.2f}万元")
    print(f"  累计研发投入: {total_rnd:,.2f}万元")

# ④关联性分析
print("\n" + "=" * 80)
print("④【持续增长与研发投入的关联性分析】")
print("=" * 80)

# 计算营收增长总额和研发投入总额的关系
print("\n公司层面关联性：")
print(f"{'公司代码':<10} {'公司名称':<15} {'CAGR(%)':<10} {'研发累计(万元)':<15} {'研发强度(%)':<12}")
print("-" * 70)

growth_amounts = []
rnd_amounts = []

for company in growing_companies:
    growth_amount = company['rev_2025q3'] - company['rev_2023q3']
    rnd_intensity = (company['total_rnd'] / (company['rev_2023q3'] + company['rev_2024q3'] + company['rev_2025q3'])) * 100
    
    growth_amounts.append(growth_amount)
    rnd_amounts.append(company['total_rnd'])
    
    print(f"{company['stock_code']:<10} {company['stock_abbr']:<15} {company['cagr']:<10.2f} {company['total_rnd']:<15,.2f} {rnd_intensity:<12.2f}%")

# 计算相关系数
correlation = np.corrcoef(cagr_list, [c['total_rnd'] for c in growing_companies])[0, 1]

print(f"\n整体分析：")
print(f"  CAGR与研发投入的相关系数: {correlation:.4f}")
print(f"  平均CAGR: {avg_cagr:.2f}%")
print(f"  平均研发投入: {np.mean([c['total_rnd'] for c in growing_companies]):,.2f}万元")

# 按CAGR排序
growing_companies_sorted = sorted(growing_companies, key=lambda x: x['cagr'], reverse=True)

print("\n【TOP 3 高增长公司】")
for i, company in enumerate(growing_companies_sorted[:3], 1):
    print(f"{i}. {company['stock_code']} - {company['stock_abbr']}: CAGR {company['cagr']:.2f}%, 研发投入 {company['total_rnd']:,.2f}万元")
