import subprocess
import sys
from pathlib import Path

src_dir = Path(__file__).parent / "src"
utils_dir = Path(__file__).parent / "utils"

steps = [
    ("数据预处理", f"python {src_dir / 'preprocess.py'}"),
    ("第一问分析", f"python {src_dir / 'analysis.py'}"),
    ("第二问寿命预测", f"python {src_dir / 'model.py'}"),
    ("第三/四问优化与敏感性", f"python {src_dir / 'optimize.py'}"),
    ("生成图表", f"python {utils_dir / 'plot.py'}"),
    #("生成论文初稿", f"python {utils_dir / 'generate_paper.py'}"),
]

for name, cmd in steps:
    print(f"\n===== {name} =====")
    ret = subprocess.run(cmd, shell=True, cwd=Path(__file__).parent)
    if ret.returncode != 0:
        print(f"警告：{name} 可能未成功完成，返回码 {ret.returncode}")
print("\n全部流程执行完毕！")