from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

DEVICE_IDS = [f"A_{i}" for i in range(1, 11)]

ANALYSIS_START = "2024-04-01"
ANALYSIS_END   = "2026-04-01"
START_DATE     = "2022-04-01"

SMALL_MAINT_MIN = 3
SMALL_MAINT_MAX = 5

CLEANED_FILE = PROCESSED_DIR / "cleaned_data.csv"