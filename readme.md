```markdown
# 过滤设备监测建模项目

## 项目简介
2026年北京高校数学建模校际联赛 A 题「过滤设备监测」的完整代码实现。  
涵盖数据预处理、透水率规律分析、寿命预测、维护方案优化及敏感性分析。  
运行 `main.py` 可一键生成所有结果和图表。

## 项目结构
```
EQUIPMENT_MONITORING/          # 项目根目录（可自由命名）
├── config.py                  # 全局路径与参数（自动基于项目根目录）
├── main.py                    # 一键运行所有模块
├── data/
│   ├── raw/                   # 原始附件1.xlsx、附件2.xlsx
│   │   ├── 附件1.xlsx
│   │   └── 附件2.xlsx
│   └── processed/             # 清洗后日频数据
│       └── cleaned_data.csv
├── src/
│   ├── preprocess.py          # 数据预处理（前向填充、维护标记）
│   ├── analysis.py            # 第一问：衰减率、季节效应、维护增益
│   ├── model.py               # 第二问：寿命预测模型
│   └── optimize.py            # 第三问、第四问：维护优化与敏感性分析
├── utils/
│   └── plot.py                # 论文图表生成
└── results/
    ├── figures/               # 5张论文用图
    │   ├── time_series_A1.png
    │   ├── seasonal.png
    │   ├── life_decay.png
    │   ├── optimal_thresholds.png
    │   └── sensitivity_heatmap.png
    ├── decay_rates.csv        # 各设备自然衰减率
    ├── indicators.csv         # 第一问关键指标汇总
    ├── life_predictions_final.csv  # 第二问寿命预测结果
    ├── optimal_maintenance.csv    # 第三问最优维护方案
    ├── seasonal_effect.csv    # 季节效应（月均偏离）
    └── sensitivity_analysis.csv   # 第四问成本波动敏感性
```

## 环境配置（队友必读）
1. **安装 Python 3.9 或以上版本**  
   推荐 [Anaconda](https://www.anaconda.com) 或从 [python.org](https://www.python.org) 下载。
2. **安装依赖库**  
   打开终端，进入项目根目录，执行：
   ```bash
   pip install pandas numpy scipy openpyxl matplotlib
   ```
   如果使用 Anaconda，也可用：
   ```bash
   conda install pandas numpy scipy openpyxl matplotlib
   ```
3. **确认数据文件**  
   确保 `data/raw/` 内包含 `附件1.xlsx` 和 `附件2.xlsx`，否则程序会报错。

## 如何运行
- 在终端的 **项目根目录** 下执行：
  ```bash
  python main.py
  ```
- 等待约 15 秒，所有结果（CSV 和图片）将自动更新在 `results/` 目录下。
- **注意**：不要进入 `src/` 或 `utils/` 目录执行脚本，务必保持在根目录。

## 路径兼容性说明
- 本项目所有路径均基于 **项目根目录自动定位**，无需手动修改任何配置。
- `config.py` 中通过 `Path(__file__).resolve().parent` 确定根目录，其他脚本均使用 `config.PROJECT_ROOT` 构建绝对路径。
- **因此，只要保持整个文件夹结构完整，无论在谁的电脑上、磁盘位置如何，均可直接运行。**

## 各模块功能与输出
| 模块 | 脚本 | 主要输出 | 关键结论 |
|------|------|----------|----------|
| 数据预处理 | `preprocess.py` | `cleaned_data.csv` | 日频前向填充，标定维护事件 |
| 第一问：规律分析 | `analysis.py` | `decay_rates.csv`, `indicators.csv`, `seasonal_effect.csv` | 平均月衰减 -11.11，中维护增益 19.53，大维护增益 16.58，季节波动幅度 31.21 |
| 第二问：寿命预测 | `model.py` | `life_predictions_final.csv` | 10台过滤器总寿命 5.15~7.46 年 |
| 第三问：维护优化 | `optimize.py` | `optimal_maintenance.csv` | 最优策略仅需中维护，阈值动态45~96 |
| 第四问：敏感性分析 | `optimize.py`（同文件） | `sensitivity_analysis.csv` | 设备价格和维护成本波动时策略稳定 |
| 图表生成 | `utils/plot.py` | `figures/` 下5张PNG | 可直接插入论文 |

## 常见问题排查
- **报错 `ModuleNotFoundError`**：请检查是否安装依赖，手动安装上述库。
- **报错找不到文件**：确认 `data/raw/` 中有 `附件1.xlsx` 和 `附件2.xlsx`，且终端工作目录为项目根目录。
- **图表中文显示为方块**：字体问题，可在 `plot.py` 中删除 `plt.rcParams['font.sans-serif']` 行，或安装 SimHei 字体。
- **运行 `main.py` 后部分步骤跳过**：查看控制台错误信息，多半是路径或数据缺失。

## 论文写作参考
- **建模手**：需复核损伤参数（`DAMAGE_MED = 0.002`, `DAMAGE_LARGE = 0.005`），并在论文中解释大维护未被触发的原因，或讨论引入强制大维护的必要性。
- **论文手**：直接使用 `results/` 下的表格数据和 `figures/` 下的图片，建议论文结构包括：
  - 摘要
  - 问题重述
  - 模型假设与符号说明
  - 数据预处理
  - 问题一：规律分析
  - 问题二：寿命预测
  - 问题三：维护优化
  - 问题四：敏感性分析
  - 模型评价与改进

## 后续优化计划
当前版本已完成所有题目要求的计算，后期优化点（如指标评估、模型对比等）将在期中考试后集中讨论添加。

如有参数或图表需要调整，直接修改对应脚本后重新运行 `main.py` 即可刷新全部结果。
```