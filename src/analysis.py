import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import config

print("===== 分析模块自检开始 =====")

# ---------------------- 读取原始数据 ----------------------
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

maint = pd.read_excel(config.RAW_DIR / "附件2.xlsx")
maint.columns = ['device', 'date', 'type']
maint['date'] = pd.to_datetime(maint['date'])
maint['device'] = maint['device'].astype(str).str.replace(r'^A(\d+)$', r'A_\1', regex=True)
type_dict = {'中维护': 'medium', '大维护': 'large'}
maint['type'] = maint['type'].map(type_dict)

# 删除透水率缺失的行（如果有）
raw = raw.dropna(subset=['per'])

# ---------------------- 1. 自然衰减率（基于维护划分区间） ----------------------
def decay_by_intervals(dev_raw, dev_maint):
    """在两次大/中维护之间计算每日衰减量（负值），取中位数"""
    df = dev_raw.sort_values('time')
    # 获取所有维护日期（大/中），包括开始和结束日期
    maint_dates = sorted(dev_maint['date'].tolist())
    # 如果某设备维护记录为空，则对整个时间段计算
    if not maint_dates:
        intervals = [(df['time'].min(), df['time'].max())]
    else:
        intervals = []
        # 起始到第一次维护
        if df['time'].min() < maint_dates[0]:
            intervals.append((df['time'].min(), maint_dates[0]))
        # 维护之间
        for i in range(len(maint_dates)-1):
            intervals.append((maint_dates[i], maint_dates[i+1]))
        # 最后一次维护到结束
        if df['time'].max() > maint_dates[-1]:
            intervals.append((maint_dates[-1], df['time'].max()))
    
    daily_drops = []
    for start, end in intervals:
        mask = (df['time'] >= start) & (df['time'] <= end)
        seg = df[mask]
        if len(seg) >= 2:
            seg = seg.sort_values('time')
            t_diff = (seg['time'].iloc[-1] - seg['time'].iloc[0]).total_seconds() / 86400.0
            p_diff = seg['per'].iloc[-1] - seg['per'].iloc[0]
            if t_diff > 0.5 and p_diff < 0:   # 区间至少0.5天且透水率下降
                daily_drops.append(p_diff / t_diff)
    if daily_drops:
        return np.median(daily_drops)   # 负值，单位 /天
    else:
        return np.nan

decay_dict = {}
for dev in config.DEVICE_IDS:
    dev_raw = raw[raw['device'] == dev].sort_values('time')
    dev_maint = maint[maint['device'] == dev]
    daily = decay_by_intervals(dev_raw, dev_maint)
    decay_dict[dev] = {
        '日均自然衰减 (unit/day)': daily,
        '月均自然衰减 (unit/month)': daily * 30.44 if not np.isnan(daily) else np.nan
    }
decay_df = pd.DataFrame(decay_dict).T
print("\n===== 各设备长期自然衰减率（维护区间中位数）=====")
print(decay_df)

# ---------------------- 2. 维护增益（前后最近有效记录） ----------------------
def gain_robust(dev_raw, dev_maint):
    gains = {'medium': [], 'large': []}
    df = dev_raw.sort_values('time')
    for _, row in dev_maint.iterrows():
        m_date = row['date']
        m_type = row['type']
        # 前：维护前的最后一个有效记录
        before = df[df['time'] < m_date]
        if before.empty:
            continue
        per_before = before.iloc[-1]['per']
        # 后：维护后第一个有效记录（不限于当天）
        after = df[df['time'] > m_date]   # 严格大于维护日期
        if after.empty:
            continue
        per_after = after.iloc[0]['per']
        gain = per_after - per_before
        if gain > 0:   # 只保留正增益
            gains[m_type].append(gain)
    avg = {}
    for mtype in ['medium', 'large']:
        if gains[mtype]:
            avg[mtype] = np.mean(gains[mtype])
        else:
            avg[mtype] = np.nan
    return avg

gain_summary = {}
for dev in config.DEVICE_IDS:
    dev_raw = raw[raw['device'] == dev]
    dev_maint = maint[maint['device'] == dev]
    gain_summary[dev] = gain_robust(dev_raw, dev_maint)

medium_all = [g['medium'] for g in gain_summary.values() if not np.isnan(g['medium'])]
large_all = [g['large'] for g in gain_summary.values() if not np.isnan(g['large'])]
print("\n===== 维护平均增益 =====")
print(f"中维护事件数: {len(medium_all)}, 平均增益: {np.mean(medium_all):.4f}" if medium_all else "中维护: 无法计算")
print(f"大维护事件数: {len(large_all)}, 平均增益: {np.mean(large_all):.4f}" if large_all else "大维护: 无法计算")

# 自检：打印一台设备的增益样本
print("\n[自检] A_1 维护增益明细（前5次）:")
a1_maint = maint[maint['device'] == 'A_1'].iloc[:5]
for _, row in a1_maint.iterrows():
    m_date = row['date']
    before = raw[(raw['device'] == 'A_1') & (raw['time'] < m_date)]
    after = raw[(raw['device'] == 'A_1') & (raw['time'] > m_date)]
    if not before.empty and not after.empty:
        per_before = before.iloc[-1]['per']
        per_after = after.iloc[0]['per']
        print(f"{m_date.date()} {row['type']}: 前 {per_before:.2f} -> 后 {per_after:.2f}, 增益 {per_after-per_before:.2f}")

# ---------------------- 3. 季节性效应 ----------------------
raw['month'] = raw['time'].dt.month
monthly = raw.groupby(['device', 'month'])['per'].mean().reset_index()
monthly['dev_mean'] = monthly.groupby('device')['per'].transform('mean')
monthly['deviation'] = monthly['per'] - monthly['dev_mean']
seasonal = monthly.groupby('month')['deviation'].mean()
print("\n===== 季节性效应 =====")
print(seasonal)

# ---------------------- 4. 汇总指标与自检 ----------------------
indicators = {
    '设备平均月自然衰减率': decay_df['月均自然衰减 (unit/month)'].mean(),
    '季节性波动幅度': seasonal.max() - seasonal.min(),
    '中维护平均增益': np.mean(medium_all) if medium_all else np.nan,
    '大维护平均增益': np.mean(large_all) if large_all else np.nan,
}
print("\n===== 透水率变化影响指标 =====")
for k, v in indicators.items():
    print(f"{k}: {v:.4f}")

warnings = []
if np.isnan(indicators['中维护平均增益']) or indicators['中维护平均增益'] < 0:
    warnings.append("中维护增益异常")
if np.isnan(indicators['大维护平均增益']) or indicators['大维护平均增益'] < 0:
    warnings.append("大维护增益异常")
if indicators['设备平均月自然衰减率'] > 0:
    warnings.append("平均衰减率为正，趋势异常")
if warnings:
    print("\n[自检警告]")
    for w in warnings:
        print(f" - {w}")
else:
    print("\n[自检通过] 所有指标在合理范围内。")

# 保存
output_dir = Path(config.PROJECT_ROOT) / "results"
output_dir.mkdir(exist_ok=True)
decay_df.to_csv(output_dir / "decay_rates.csv")
seasonal.to_csv(output_dir / "seasonal_effect.csv")
pd.DataFrame([indicators]).to_csv(output_dir / "indicators.csv", index=False)
print(f"\n结果已保存至 {output_dir}")