"""Tahmin girdilerinin tek kaynağı.

Tarayıcı bu girdileri kendi hesaplıyordu ve 19 alanın 10'u eğitim setinden farklı
çıkıyordu: makro `*_5d` alanları gözlem sayısıyla, `*_20d` alanları ise altın
barının değil FRED serisinin son tarihine göre geriye bakıyordu. Model her
tahminde eğitildiğinden başka bir girdi görüyordu. Artık kanonik vektör burada
üretilir; kaynağı eğitim CSV'sinin son satırı, yani `xau_dataset_service` ile
birebir aynı formül.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..config import ROOT
from .xau_dataset_service import FEATURES

DATASET_PATH = ROOT / "data" / "xauusd_training_5y.csv"


def latest_features(dataset_path: Path = DATASET_PATH) -> dict:
    """Veri setinin son satırındaki girdi vektörü, tarihi ve kapanışı."""
    with dataset_path.open(encoding="utf-8") as source:
        last = None
        for row in csv.DictReader(source):
            last = row
    if last is None:
        raise ValueError("XAU/USD veri seti boş; önce veri seti üretilmeli")

    missing = [name for name in FEATURES if last.get(name) in (None, "")]
    if missing:
        raise ValueError(f"Veri setinde eksik girdi: {', '.join(missing)}")

    return {
        "date": last["date"],
        "price": float(last["xauusd_close"]),
        "features": {name: float(last[name]) for name in FEATURES},
    }
