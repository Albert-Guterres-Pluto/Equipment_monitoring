import matplotlib
matplotlib.use('Agg')   # 使用非 GUI 后端，只保存图片，不弹窗
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import config

sns.set_style("whitegrid")
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用于显示中文
plt.rcParams['axes.unicode_minus'] = False

output_dir = config.PROJECT_ROOT / "results" / "figures"
output_dir.mkdir(parents=True, exist_ok=True)

# ==================== 图1：透水率时间序列示例（A_1） ====================
df = pd.read_csv(config.CLEANED_FILE, parse_dates=['date'])
dev_data = df[df['device'] == 'A_1']
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(dev_data['date'], dev_data['per'], linewidth=0.8, label='透水率')
# 标注中维护和大维护
medium = dev_data[dev_data['type'] == 'medium']
large = dev_data[dev_data['type'] == 'large']
ax.scatter(medium['date'], medium['per'], color='green', s=20, label='中维护', zorder=5)
ax.scatter(large['date'], large['per'], color='red', s=30, marker='^', label='大维护', zorder=5)
ax.axhline(37, color='gray', linestyle='--', label='失效阈值')
ax.set_title('A_1 过滤器透水率变化与维护事件')
ax.set_xlabel('日期')
ax.set_ylabel('透水率')
ax.legend()
fig.autofmt_xdate()
plt.tight_layout()
plt.savefig(output_dir / "time_series_A1.png", dpi=150)
plt.close()

# ==================== 图2：季节性效应 ====================
seasonal = pd.read_csv(config.PROJECT_ROOT / "results" / "seasonal_effect.csv", index_col=0).squeeze()
fig, ax = plt.subplots(figsize=(8, 4))
months = range(1, 13)
ax.bar(months, seasonal.values, color=['#1f77b4' if v>0 else '#d62728' for v in seasonal.values])
ax.set_title('不同月份的季节性效应（月平均偏离设备均值）')
ax.set_xlabel('月份')
ax.set_ylabel('透水率偏离值')
ax.axhline(0, color='black', linewidth=0.8)
plt.tight_layout()
plt.savefig(output_dir / "seasonal.png", dpi=150)
plt.close()

# ==================== 图3：各设备衰减率与寿命 ====================
decay = pd.read_csv(config.PROJECT_ROOT / "results" / "decay_rates.csv", index_col=0)
life = pd.read_csv(config.PROJECT_ROOT / "results" / "life_predictions_final.csv")
merged = life.merge(decay, left_on='设备', right_index=True)

fig, ax1 = plt.subplots(figsize=(10, 5))
x = np.arange(len(merged))
width = 0.4
ax1.bar(x, merged['总寿命(年)'], width, label='总寿命 (年)', color='steelblue')
ax1.set_ylabel('总寿命 (年)')
ax2 = ax1.twinx()
ax2.plot(x, merged['月均自然衰减 (unit/month)'] * -1, 'ro-', label='月均衰减率 (取反)')
ax2.set_ylabel('月均衰减率 (unit/月)')
ax1.set_xticks(x)
ax1.set_xticklabels(merged['设备'])
ax1.set_title('各设备总寿命与衰减率对比')
fig.legend(loc="upper right", bbox_to_anchor=(1,1), bbox_transform=ax1.transAxes)
plt.tight_layout()
plt.savefig(output_dir / "life_decay.png", dpi=150)
plt.close()

# ==================== 图4：最优维护阈值对比 ====================
opt = pd.read_csv(config.PROJECT_ROOT / "results" / "optimal_maintenance.csv")
fig, ax = plt.subplots(figsize=(8, 4))
x = np.arange(len(opt))
ax.bar(x, opt['最优中维护阈值'], label='中维护阈值', color='green', alpha=0.7)
ax.bar(x, opt['最优大维护阈值'], label='大维护阈值', color='red', alpha=0.7)
ax.set_xticks(x)
ax.set_xticklabels(opt['设备'])
ax.set_title('各设备最优维护阈值')
ax.set_ylabel('透水率阈值')
ax.legend()
plt.tight_layout()
plt.savefig(output_dir / "optimal_thresholds.png", dpi=150)
plt.close()

# ==================== 图5：敏感性热力图（第四问） ====================
sens = pd.read_csv(config.PROJECT_ROOT / "results" / "sensitivity_analysis.csv")
pivot = sens.pivot_table(index='维护成本因子', columns='设备价格因子', values='年均成本(万元)', aggfunc='mean')
fig, ax = plt.subplots(figsize=(7, 5))
sns.heatmap(pivot, annot=True, fmt=".1f", cmap="YlOrRd", ax=ax)
ax.set_title('年均成本敏感性（设备 A_1）')
plt.tight_layout()
plt.savefig(output_dir / "sensitivity_heatmap.png", dpi=150)
plt.close()

print("所有图表已保存至", output_dir)