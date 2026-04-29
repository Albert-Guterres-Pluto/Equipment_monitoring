import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import config

print("===== 分析模块自检开始 =====")

# ---------------------- 读取数据 ----------------------
xls = pd.ExcelFile(config.RAW_DIR / "附件1.xlsx")
raw_list = []
for sheet in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=sheet)
    df.columns = ['time', 'per']
    df['device'] = sheet
    raw_list.append(df)

raw = pd.concat(raw_list, ignore_index=True)
raw['time'] = pd.to_datetime(raw['time'])
raw = raw.sort_values(['device', 'time']).reset_index(drop=True)
raw = raw.dropna(subset=['per'])

maint = pd.read_excel(config.RAW_DIR / "附件2.xlsx")
maint.columns = ['device', 'date', 'type']
maint['date'] = pd.to_datetime(maint['date'])
maint['device'] = maint['device'].astype(str).str.replace(r'^A(\d+)$', r'A_\1', regex=True)
maint['type'] = maint['type'].map({'中维护': 'medium', '大维护': 'large'})

# ---------------------- 1. 自然衰减率 ----------------------
def decay_by_intervals(dev_raw, dev_maint):
    df = dev_raw.sort_values('time')
    maint_dates = sorted(dev_maint['date'].tolist())

    if not maint_dates:
        intervals = [(df['time'].min(), df['time'].max())]
    else:
        intervals = []
        if df['time'].min() < maint_dates[0]:
            intervals.append((df['time'].min(), maint_dates[0]))

        for i in range(len(maint_dates)-1):
            intervals.append((maint_dates[i], maint_dates[i+1]))

        if df['time'].max() > maint_dates[-1]:
            intervals.append((maint_dates[-1], df['time'].max()))

    daily_drops = []
    for start, end in intervals:
        seg = df[(df['time'] >= start) & (df['time'] <= end)]
        if len(seg) >= 2:
            t = (seg['time'].iloc[-1] - seg['time'].iloc[0]).total_seconds() / 86400
            p = seg['per'].iloc[-1] - seg['per'].iloc[0]
            if t > 0.5 and p < 0:
                daily_drops.append(p / t)

    return np.median(daily_drops) if daily_drops else np.nan

decay_dict = {}
for dev in config.DEVICE_IDS:
    d = decay_by_intervals(
        raw[raw['device'] == dev],
        maint[maint['device'] == dev]
    )
    decay_dict[dev] = {
        '日均自然衰减': d,
        '月均自然衰减': d * 30.44 if not np.isnan(d) else np.nan
    }

decay_df = pd.DataFrame(decay_dict).T
print("\n===== 自然衰减率 =====")
print(decay_df)

# ---------------------- 2. 维护效应（核心） ----------------------
def maintenance_effect(dev_raw, dev_maint, window=3):
    results = {
        'medium': {'gain': [], 'delta_d': []},
        'large': {'gain': [], 'delta_d': []}
    }

    df = dev_raw.sort_values('time').reset_index(drop=True)

    for _, row in dev_maint.iterrows():
        m_date = row['date']
        m_type = row['type']

        # 关键：严格用“维护之后”的点
        idx = df[df['time'] > m_date].index
        if len(idx) == 0:
            continue
        i = idx[0]

        if i - window < 0 or i + window >= len(df):
            continue

        before = df.iloc[i-window:i]['per']
        after = df.iloc[i:i+window]['per']

        # 增益（窗口平均）
        gain = after.mean() - before.mean()

        # 斜率
        d_before = (before.iloc[-1] - before.iloc[0]) / window
        d_after = (after.iloc[-1] - after.iloc[0]) / window

        delta_d = d_after - d_before

        results[m_type]['gain'].append(gain)
        results[m_type]['delta_d'].append(delta_d)

    summary = {}
    for mtype in ['medium', 'large']:
        summary[mtype] = {
            'gain': np.mean(results[mtype]['gain']) if results[mtype]['gain'] else np.nan,
            'delta_d': np.mean(results[mtype]['delta_d']) if results[mtype]['delta_d'] else np.nan
        }

    return summary

effect_summary = {}
detail_rows = []

for dev in config.DEVICE_IDS:
    dev_raw = raw[raw['device'] == dev]
    dev_maint = maint[maint['device'] == dev]

    res = maintenance_effect(dev_raw, dev_maint)
    effect_summary[dev] = res

# 汇总
med_gain_all, med_dd_all = [], []
large_gain_all, large_dd_all = [], []

for dev, v in effect_summary.items():
    if not np.isnan(v['medium']['gain']):
        med_gain_all.append(v['medium']['gain'])
        med_dd_all.append(v['medium']['delta_d'])
    if not np.isnan(v['large']['gain']):
        large_gain_all.append(v['large']['gain'])
        large_dd_all.append(v['large']['delta_d'])

print("\n===== 维护增益 =====")
print(f"中维护: {np.mean(med_gain_all):.4f}（样本{len(med_gain_all)}）" if med_gain_all else "中维护: 无")
print(f"大维护: {np.mean(large_gain_all):.4f}（样本{len(large_gain_all)}）" if large_gain_all else "大维护: 无")

print("\n===== 维护损伤 Δd（负值=变差） =====")
print(f"中维护 Δd: {np.mean(med_dd_all):.6f}" if med_dd_all else "中维护: 无")
print(f"大维护 Δd: {np.mean(large_dd_all):.6f}" if large_dd_all else "大维护: 无")

# ---------------------- 3. 季节性 ----------------------
raw['month'] = raw['time'].dt.month
monthly = raw.groupby(['device', 'month'])['per'].mean().reset_index()
monthly['dev_mean'] = monthly.groupby('device')['per'].transform('mean')
monthly['deviation'] = monthly['per'] - monthly['dev_mean']
seasonal = monthly.groupby('month')['deviation'].mean()

print("\n===== 季节性 =====")
print(seasonal)

# ---------------------- 4. 指标 ----------------------
indicators = {
    '平均月衰减': decay_df['月均自然衰减'].mean(),
    '季节波动': seasonal.max() - seasonal.min(),
    '中维护增益': np.mean(med_gain_all),
    '大维护增益': np.mean(large_gain_all),
    '中维护Δd': np.mean(med_dd_all),
    '大维护Δd': np.mean(large_dd_all),
}

print("\n===== 指标汇总 =====")
for k, v in indicators.items():
    print(f"{k}: {v:.4f}")

# ---------------------- 保存 ----------------------
output_dir = Path(config.PROJECT_ROOT) / "results"
output_dir.mkdir(exist_ok=True)

decay_df.to_csv(output_dir / "decay_rates.csv")
seasonal.to_csv(output_dir / "seasonal_effect.csv")
pd.DataFrame([indicators]).to_csv(output_dir / "indicators.csv", index=False)

print(f"\n结果已保存至 {output_dir}")