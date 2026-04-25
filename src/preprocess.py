import sys
from pathlib import Path
# 将项目根目录加入搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import config

# ========== 1. 读取透水率数据 ==========
def load_permeability():
    file_path = config.RAW_DIR / "附件1.xlsx"
    xls = pd.ExcelFile(file_path)
    frames = []
    for dev in config.DEVICE_IDS:
        df = pd.read_excel(xls, sheet_name=dev)
        df.columns = ['time', 'per']
        df['device'] = dev
        frames.append(df)
    df_all = pd.concat(frames, ignore_index=True)
    df_all['time'] = pd.to_datetime(df_all['time'])
    df_all = df_all.sort_values(['device', 'time'])

    mask = (df_all['time'] >= config.ANALYSIS_START) & (df_all['time'] <= config.ANALYSIS_END)
    return df_all[mask].reset_index(drop=True)

# ========== 2. 生成每日前向填充数据 ==========
def to_daily(df):
    date_range = pd.date_range(config.ANALYSIS_START, config.ANALYSIS_END, freq='D')
    daily_frames = []
    for dev, grp in df.groupby('device'):
        grp = grp.set_index('time')['per']
        grp_daily = grp.reindex(date_range, method='ffill')
        grp_daily = grp_daily.bfill()   # 开头无数据用后一值填充
        daily_frames.append(pd.DataFrame({
            'date': date_range,
            'per': grp_daily.values,
            'device': dev
        }))
    return pd.concat(daily_frames, ignore_index=True)

# ========== 3. 读取并扩展维护记录 ==========
def load_maintenance():
    # 读取真实维护
    df_maint = pd.read_excel(config.RAW_DIR / "附件2.xlsx")
    df_maint.columns = ['device', 'date', 'type']
    df_maint['date'] = pd.to_datetime(df_maint['date'])

    # ★ 将设备编号转换为与附件1一致的格式（例如 A1 -> A_1）
    df_maint['device'] = df_maint['device'].astype(str).str.strip()
    # 假设编号格式是 “A” + 数字，统一加下划线
    df_maint['device'] = df_maint['device'].str.replace(
        r'^A(\d+)$', r'A_\1', regex=True
    )

    type_map = {'中维护': 'medium', '大维护': 'large'}
    df_maint['type'] = df_maint['type'].map(type_map)

    # 生成小维护记录（随机间隔3~5天，从投用日到分析结束）
    small_records = []
    np.random.seed(42)
    for dev in config.DEVICE_IDS:
        current = pd.Timestamp(config.START_DATE)
        end = pd.Timestamp(config.ANALYSIS_END)
        while current <= end:
            small_records.append({'device': dev, 'date': current, 'type': 'small'})
            current += pd.Timedelta(days=np.random.randint(config.SMALL_MAINT_MIN,
                                                           config.SMALL_MAINT_MAX + 1))
    df_small = pd.DataFrame(small_records)
    df_maint = pd.concat([df_maint, df_small], ignore_index=True)
    df_maint['date'] = pd.to_datetime(df_maint['date'])

    # 同一天有多条时保留等级最高者
    priority = {'large': 3, 'medium': 2, 'small': 1}
    df_maint['priority'] = df_maint['type'].map(priority)
    df_maint = df_maint.sort_values('priority', ascending=False)
    df_maint = df_maint.drop_duplicates(['device', 'date'], keep='first')
    df_maint = df_maint.drop('priority', axis=1)

    return df_maint

# ========== 4. 合并数据并添加特征 ==========
def merge_and_add_features(daily_df, maint_df):
    merged = daily_df.merge(maint_df, on=['device', 'date'], how='left')
    merged['type'] = merged['type'].fillna('none')
    merged['is_maintenance'] = (merged['type'] != 'none').astype(int)

    # 时间特征
    merged['month'] = merged['date'].dt.month
    merged['season'] = merged['month'].apply(
        lambda m: 1 if m in [3,4,5] else (2 if m in [6,7,8] else (3 if m in [9,10,11] else 4))
    )
    merged['day_of_year'] = merged['date'].dt.dayofyear

    # 距上次维护天数
    merged = merged.sort_values(['device', 'date'])
    def calc_days_since(group):
        maint_dates = group['date'].where(group['is_maintenance'] == 1)
        last_maint = maint_dates.ffill()
        days = (group['date'] - last_maint).dt.days
        return days.fillna(9999)
    merged['days_since_last_maint'] = (
        merged.groupby('device')[['date', 'is_maintenance']]
              .apply(calc_days_since)
              .values
    )
    return merged

# ========== 主流程 ==========
def main():
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("Reading permeability data...")
    df_perm = load_permeability()

    print("Creating daily time series with forward fill...")
    df_daily = to_daily(df_perm)

    print("Loading and generating maintenance log...")
    df_maint = load_maintenance()

    print("Merging and adding features...")
    df_final = merge_and_add_features(df_daily, df_maint)

    print(f"Final shape: {df_final.shape}")
    print(f"Devices: {df_final['device'].unique()}")
    print(f"Date range: {df_final['date'].min()} to {df_final['date'].max()}")

    df_final.to_csv(config.CLEANED_FILE, index=False)
    print(f"Saved cleaned data to {config.CLEANED_FILE}")

if __name__ == "__main__":
    main()