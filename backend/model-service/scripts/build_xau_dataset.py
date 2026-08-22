#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.xau_dataset_service import write_csv


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "xauusd_training_5y.csv"
    count = write_csv(target)
    print(f"{count} satır yazıldı: {target}")
