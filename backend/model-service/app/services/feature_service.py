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
from .freshness import frozen_features
from .xau_dataset_service import FEATURES

# Teknik girdiler fiyattan türer ve sabit kalmaları anlamlıdır (ör. sıfır
# zirveden düşüş); donmuşluk yalnız makro blokta aranır.
MACRO_FEATURES = FEATURES[8:]

DATASET_PATH = ROOT / "data" / "xauusd_training_5y.csv"


_frozen_cache: tuple[float, tuple[str, ...]] | None = None


def frozen_now(dataset_path: Path = DATASET_PATH) -> tuple[str, ...]:
    """Şu an donmuş makro girdiler; veri seti değişmedikçe yeniden okunmaz.

    Kararı sunucu verir: istemciden gelen listeye güvenmek, çağıranın onu
    atlamasıyla tahminin sessizce eski davranışa dönmesi demekti.
    """
    global _frozen_cache
    try:
        stamp = dataset_path.stat().st_mtime
    except OSError:
        return ()                       # veri seti yoksa nötrleme de yok
    if _frozen_cache and _frozen_cache[0] == stamp:
        return _frozen_cache[1]
    try:
        with dataset_path.open(encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
    except OSError:
        return ()
    result = frozen_features(rows, MACRO_FEATURES)
    _frozen_cache = (stamp, result)
    return result


def latest_features(dataset_path: Path = DATASET_PATH) -> dict:
    """Veri setinin son satırındaki girdi vektörü, tarihi ve kapanışı."""
    with dataset_path.open(encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    last = rows[-1] if rows else None
    if last is None:
        raise ValueError("XAU/USD veri seti boş; önce veri seti üretilmeli")

    missing = [name for name in FEATURES if last.get(name) in (None, "")]
    if missing:
        raise ValueError(f"Veri setinde eksik girdi: {', '.join(missing)}")

    return {
        "date": last["date"],
        "price": float(last["xauusd_close"]),
        "features": {name: float(last[name]) for name in FEATURES},
        # Uzun süredir değişmeyen girdiler tahmin edilen dönem hakkında bilgi
        # taşımaz; tahmin anında nötrlenmeleri için bildiriliyor.
        "frozen": list(frozen_features(rows, MACRO_FEATURES)),
    }
