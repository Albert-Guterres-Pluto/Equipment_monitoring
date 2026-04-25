import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import config
import time

# ==================== 读取第一问结果 ====================
decay_df = pd.read_csv(config.PROJECT_ROOT / "results" / "decay_rates.csv", index_col=0)
seasonal = pd.read_csv(config.PROJECT_ROOT / "results" / "seasonal_effect.csv", index_col=0).squeeze()
indicators = pd.read_csv(config.PROJECT_ROOT / "results" / "indicators.csv").iloc[0]

GAIN_MED = indicators['中维护平均增益']
GAIN_LARGE = indicators['大维护平均增益']
# 季节效应转为日值（保持原算法）
season_daily = seasonal / 30.0
base_decay = decay_df['日均自然衰减 (unit/day)'].to_dict()

# 损伤参数（适中，确保维护有代价但不过分）
DAMAGE_MED = 0.002      # 每次中维护使日均衰减率增加（更负）
DAMAGE_LARGE = 0.005    # 每次大维护增加

PRICE_FILTER = 300e4
COST_MED = 3e4
COST_LARGE = 12e4

# ==================== 读取原始数据 ====================
xls = pd.ExcelFile(config.RAW_DIR / "附件1.xlsx")
raw_list = []
for sheet in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=sheet)
    df.columns = ['time', 'per']
    df['device'] = sheet
    raw_list.append(df)
raw_df = pd.concat(raw_list, ignore_index=True)
raw_df['time'] = pd.to_datetime(raw_df['time'])

def get_current_P(device, ref_date='2026-04-01'):
    dev_dat = raw_df[raw_df['device'] == device]
    mask = (dev_dat['time'] >= pd.Timestamp(ref_date) - pd.DateOffset(days=7)) & \
           (dev_dat['time'] <= pd.Timestamp(ref_date) + pd.DateOffset(days=7))
    vals = dev_dat[mask]['per']
    return float(vals.median()) if len(vals) > 0 else float(dev_dat['per'].iloc[-100:].median())

# ==================== 模拟器 ====================
def simulate_threshold(device, P_start, start_date, L_med, L_large,
                       max_years=20, price=PRICE_FILTER,
                       cost_med=COST_MED, cost_large=COST_LARGE):
    d0 = base_decay[device]
    start_date = pd.Timestamp(start_date)
    total_days = max_years * 365 + 10
    dates = [start_date + pd.Timedelta(days=i) for i in range(total_days)]

    P = np.zeros(total_days)
    P[0] = P_start

    med_count = 0
    large_count = 0
    last_large_day = -9999
    total_cost = 0
    fail_day = None

    for i in range(1, total_days):
        cur_date = dates[i]
        month = cur_date.month
        current_decay = d0 - DAMAGE_MED * med_count - DAMAGE_LARGE * large_count
        season_eff = season_daily.get(month, 0.0)

        new_P = P[i-1] + current_decay + season_eff

        # 维护判断
        maint_done = False
        if new_P < L_large and (i - last_large_day) >= 180:
            new_P += GAIN_LARGE
            large_count += 1
            total_cost += cost_large
            last_large_day = i
            maint_done = True
        if not maint_done and new_P < L_med:
            new_P += GAIN_MED
            med_count += 1
            total_cost += cost_med

        P[i] = new_P

        # 检查失效
        if i >= 365:
            if np.mean(P[i-364:i+1]) < 37:
                fail_day = i
                break

    if fail_day is None:
        fail_day = total_days - 1
    fail_date = dates[fail_day]
    life_years = (fail_date - pd.Timestamp('2022-04-01')).days / 365.25
    total_cost += price
    annual_cost = total_cost / life_years
    return annual_cost, med_count, large_count, fail_date

# ==================== 单设备优化 ====================
def optimize_device(device):
    P0 = get_current_P(device)
    print(f"\n优化设备 {device}，当前透水率: {P0:.1f}")

    # 根据当前透水率动态设定搜索范围
    # 中维护阈值：应低于当前值，且不低于失效阈值37
    Lm_low = max(37, int(P0) - 15)  # 最低可以比当前值低15
    Lm_high = min(85, int(P0) + 5)  # 最高略高于当前值（这样会立即触发一次中维护）
    if Lm_low >= Lm_high:
        Lm_high = Lm_low + 5
    Lm_range = np.arange(Lm_low, Lm_high, 5, dtype=int)

    # 大维护阈值：37~中维护触发值之间
    LM_range = np.arange(37, 65, 5, dtype=int)

    best_cost = np.inf
    best_params = (None, None)
    best_details = None

    for Lm in Lm_range:
        for LM in LM_range:
            if LM >= Lm:
                continue
            cost, med_n, large_n, fail = simulate_threshold(
                device, P0, '2026-04-01', int(Lm), int(LM)
            )
            if cost < best_cost:
                best_cost = cost
                best_params = (Lm, LM)
                best_details = (med_n, large_n, fail, cost)

    if best_details is None:
        print("  警告：未找到可行解，尝试扩大搜索范围。")
        # 扩大搜索再试一次
        Lm_range = np.arange(37, min(90, int(P0)+10), 5, dtype=int)
        for Lm in Lm_range:
            for LM in range(37, int(Lm), 5):
                if LM >= Lm: continue
                cost, med_n, large_n, fail = simulate_threshold(device, P0, '2026-04-01', Lm, LM)
                if cost < best_cost:
                    best_cost = cost
                    best_params = (Lm, LM)
                    best_details = (med_n, large_n, fail, cost)

    print(f"最优阈值: 中维护触发 < {best_params[0]}, 大维护触发 < {best_params[1]}")
    print(f"年均成本: {best_cost/1e4:.2f} 万元")
    print(f"中维护次数: {best_details[0]}, 大维护次数: {best_details[1]}, 失效日期: {best_details[2].date()}")

    return {
        '设备': device,
        '当前透水率': P0,
        '最优中维护阈值': best_params[0],
        '最优大维护阈值': best_params[1],
        '年均成本(万元)': best_cost / 1e4,
        '中维护次数': best_details[0],
        '大维护次数': best_details[1],
        '失效日期': best_details[2]
    }

# ==================== 主程序 ====================
if __name__ == "__main__":
    t0 = time.time()
    print("===== 第三问：最优维护方案优化 =====")

    results = []
    for dev in config.DEVICE_IDS:
        res = optimize_device(dev)
        results.append(res)

    opt_df = pd.DataFrame(results)
    out = config.PROJECT_ROOT / "results" / "optimal_maintenance.csv"
    opt_df.to_csv(out, index=False)
    print(f"\n优化完成，耗时 {time.time()-t0:.2f} 秒，结果已保存至 {out}")

    # ==================== 第四问：敏感性分析 ====================
    print("\n===== 第四问：成本波动敏感性分析 =====")
    sens_device = 'A_1'
    P0_sens = get_current_P(sens_device)

    price_factors = [0.5, 0.8, 1.0, 1.2, 1.5]
    maint_factors = [0.5, 0.8, 1.0, 1.2, 1.5]
    sens_results = []

    for pf in price_factors:
        for mf in maint_factors:
            cur_price = PRICE_FILTER * pf
            cur_cost_med = COST_MED * mf
            cur_cost_large = COST_LARGE * mf

            best_cost = np.inf
            best_Lm, best_LM = 0, 0
            # 简单网格
            for Lm in range(40, int(P0_sens)+5, 5):
                for LM in range(37, min(Lm, 60), 5):
                    if LM >= Lm: continue
                    cost, _, _, _ = simulate_threshold(
                        sens_device, P0_sens, '2026-04-01', Lm, LM,
                        price=cur_price, cost_med=cur_cost_med, cost_large=cur_cost_large
                    )
                    if cost < best_cost:
                        best_cost = cost
                        best_Lm, best_LM = Lm, LM
            sens_results.append({
                '设备价格因子': pf,
                '维护成本因子': mf,
                '最优中维护阈值': best_Lm,
                '最优大维护阈值': best_LM,
                '年均成本(万元)': best_cost / 1e4
            })
            print(f"价格因子{pf} 维护因子{mf}: 阈值({best_Lm},{best_LM}), 年均成本{best_cost/1e4:.2f}万")

    sens_df = pd.DataFrame(sens_results)
    sens_out = config.PROJECT_ROOT / "results" / "sensitivity_analysis.csv"
    sens_df.to_csv(sens_out, index=False)
    print(f"\n敏感性分析已保存至 {sens_out}")