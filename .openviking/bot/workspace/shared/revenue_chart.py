import matplotlib.pyplot as plt
import matplotlib
import numpy as np

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# 数据
years = ['2022年', '2023年', '2024年']
revenue = [18.05, 19.42, 25.78]
colors = ['#3498db', '#2ecc71', '#e74c3c']

# 创建图表
fig, ax = plt.subplots(figsize=(12, 6))

# 绘制水平柱状图
bars = ax.barh(years, revenue, color=colors, edgecolor='black', linewidth=1.5)

# 添加数值标签
for i, (bar, value) in enumerate(zip(bars, revenue)):
    ax.text(value + 0.3, bar.get_y() + bar.get_height()/2, 
            f'{value:.2f}亿元', 
            va='center', ha='left', fontsize=12, fontweight='bold')

# 设置标题和标签
ax.set_xlabel('营业收入（亿元）', fontsize=12, fontweight='bold')
ax.set_title('佐力药业近3年营业收入趋势', fontsize=14, fontweight='bold', pad=20)

# 添加网格线
ax.grid(axis='x', alpha=0.3, linestyle='--')
ax.set_axisbelow(True)

# 设置x轴范围
ax.set_xlim(0, 28)

# 优化布局
plt.tight_layout()

# 保存图表
plt.savefig('zuoli_revenue_chart.png', dpi=300, bbox_inches='tight')
print("✅ 图表已生成：zuoli_revenue_chart.png")

# 显示图表
plt.show()
