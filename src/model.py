import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import config

# -------------------- 读取第一问结果 --------------------
decay_df = pd.read_csv(config.PROJECT_ROOT / "results" / "decay_rates.csv", index_col=0)
seasonal = pd.read_csv(config.PROJECT_ROOT / "results" / "seasonal_effect.csv", index_col=0).squeeze()
indicators = pd.read_csv(config.PROJECT_ROOT / "results" / "indicators.csv").iloc[0]

GAIN_MED = indicators['中维护平均增益']
GAIN_LARGE = indicators['大维护平均增益']
# 季节效应转换为日均（原为月均偏离）
season_daily = seasonal / 30.0
season_dict_daily = season_daily.to_dict()

# 初始日均衰减率（负值）
base_decay = decay_df['日均自然衰减 (unit/day)'].to_dict()

# 损伤参数（每次维护后额外增加的衰减量）
DAMAGE_MED = 0.01      # 中维护损伤（衰减率加快，负值更负）
DAMAGE_LARGE = 0.03    # 大维护损伤

# -------------------- 读取维护记录与原始数据 --------------------
maint_raw = pd.read_excel(config.RAW_DIR / "附件2.xlsx")
maint_raw.columns = ['device', 'date', 'type']
maint_raw['date'] = pd.to_datetime(maint_raw['date'])
maint_raw['device'] = maint_raw['device'].astype(str).str.replace(r'^A(\d+)$', r'A_\1', regex=True)
maint_raw['type'] = maint_raw['type'].map({'中维护': 'medium', '大维护': 'large'})

xls = pd.ExcelFile(config.RAW_DIR / "附件1.xlsx")
raw_list = []
for sheet in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=sheet)
    df.columns = ['time', 'per']
    df['device'] = sheet
    raw_list.append(df)
raw_df = pd.concat(raw_list, ignore_index=True)
raw_df['time'] = pd.to_datetime(raw_df['time'])

# -------------------- 未来维护计划生成 --------------------
def get_future_schedule(device, start, years_ahead=40):
    """根据历史维护间隔生成未来维护日期，最多 look_ahead 年"""
    dev_maint = maint_raw[maint_raw['device'] == device]
    med_dates = sorted(dev_maint[dev_maint['type'] == 'medium']['date'])
    large_dates = sorted(dev_maint[dev_maint['type'] == 'large']['date'])

    med_int = np.median([(med_dates[i+1] - med_dates[i]).days for i in range(len(med_dates)-1)]) if len(med_dates) >= 2 else 120
    large_int = np.median([(large_dates[i+1] - large_dates[i]).days for i in range(len(large_dates)-1)]) if len(large_dates) >= 2 else 365

    end_date = start + pd.DateOffset(years=years_ahead)
    schedule = []
    # 中维护：从最后一个已知维护向后生成
    last_med = med_dates[-1] if med_dates else start - pd.DateOffset(days=med_int)
    d = last_med + pd.DateOffset(days=med_int)
    while d <= end_date:
        if d >= start:
            schedule.append({'date': d, 'type': 'medium'})
        d += pd.DateOffset(days=med_int)
    # 大维护
    last_large = large_dates[-1] if large_dates else start - pd.DateOffset(days=large_int)
    d = last_large + pd.DateOffset(days=large_int)
    while d <= end_date:
        if d >= start:
            schedule.append({'date': d, 'type': 'large'})
        d += pd.DateOffset(days=large_int)

    return pd.DataFrame(schedule) if schedule else pd.DataFrame()

# -------------------- 模拟函数 --------------------
def simulate_future(device, P_start, start_date, years=40):
    """逐日模拟，含损伤累积和日均季节效应"""
    # 初始衰减率（负）
    d0 = base_decay[device]
    # 未来维护
    fut = get_future_schedule(device, start_date, years)
    # 将维护转换为字典：日期 -> 类型
    maint_dict = {}
    if not fut.empty:
        for _, row in fut.iterrows():
            maint_dict[row['date'].strftime('%Y-%m-%d')] = row['type']

    dates = pd.date_range(start_date, start_date + pd.DateOffset(years=years), freq='D')
    P = np.zeros(len(dates))
    P[0] = P_start

    # 维护损伤累计（从0开始，因为历史损伤已体现在当前衰减率中）
    med_count = 0
    large_count = 0

    for i in range(1, len(dates)):
        cur_date = dates[i]
        m = cur_date.month
        # 当前衰减率（负值）：基础衰减 + 损伤累积（损伤使衰减更负，即减去正值）
        current_decay = d0 - DAMAGE_MED * med_count - DAMAGE_LARGE * large_count
        # 季节日效应
        season_eff = season_dict_daily.get(m, 0.0)
        
        new_P = P[i-1] + current_decay + season_eff

        # 处理维护
        maint_type = maint_dict.get(cur_date.strftime('%Y-%m-%d'))
        if maint_type == 'medium':
            new_P += GAIN_MED
            med_count += 1
        elif maint_type == 'large':
            new_P += GAIN_LARGE
            large_count += 1

        P[i] = new_P

    df = pd.DataFrame({'date': dates, 'per': P})
    # 年均透水率（过去365天滚动，至少365天才有效）
    df['yearly_avg'] = df['per'].rolling(window=365, min_periods=365).mean()
    return df

# -------------------- 当前透水率（稳健） --------------------
def get_current_P(device, ref_date='2026-04-01'):
    dev_dat = raw_df[raw_df['device'] == device]
    # 取参考日期前后7天
    mask = (dev_dat['time'] >= pd.Timestamp(ref_date) - pd.DateOffset(days=7)) & \
           (dev_dat['time'] <= pd.Timestamp(ref_date) + pd.DateOffset(days=7))
    vals = dev_dat[mask]['per']
    if len(vals) > 0:
        return vals.median()   # 中位数抗异常
    else:
        # 取整个数据最后100条的中位数
        return dev_dat['per'].iloc[-100:].median()

# -------------------- 寿命预测 --------------------
print("===== 寿命预测（修正版）=====")
results = []
for dev in config.DEVICE_IDS:
    P_now = get_current_P(dev)
    print(f"\n{dev}: 当前透水率 = {P_now:.2f}")
    sim_df = simulate_future(dev, P_now, pd.Timestamp('2026-04-01'), years=40)
    
    below = sim_df[sim_df['yearly_avg'].notna() & (sim_df['yearly_avg'] < 37)]
    if below.empty:
        fail_date = None
        life_total = np.nan
        print("  40年内未跌破37")
    else:
        fail_date = below.iloc[0]['date']
        life_total = (fail_date - pd.Timestamp('2022-04-01')).days / 365.25
        print(f"  失效日期: {fail_date.date()}, 总寿命: {life_total:.2f} 年")
    results.append({
        '设备': dev,
        '当前透水率': P_now,
        '失效日期': fail_date,
        '总寿命(年)': life_total
    })

life_df = pd.DataFrame(results)
out = config.PROJECT_ROOT / "results" / "life_predictions_final.csv"
life_df.to_csv(out, index=False)
print(f"\n结果已保存至 {out}")