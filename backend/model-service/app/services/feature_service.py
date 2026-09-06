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
import hashlib
import io
from pathlib import Path

from ..config import ROOT
from .freshness import frozen_features
from .xau_dataset_service import FEATURES
from .data_quality import (feature_vector, load_dataset_manifest, unverified_provenance,
                           validate_dataset_rows)

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
    raw = dataset_path.read_bytes()
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    validate_dataset_rows(rows)
    last = rows[-1]
    fingerprint = hashlib.sha256(raw).hexdigest()
    manifest = load_dataset_manifest(dataset_path, expected_hash=fingerprint)
    provenance = manifest.get("provenance", unverified_provenance()) if manifest else unverified_provenance()

    return {
        "date": last["date"],
        "price": float(last["xauusd_close"]),
        "features": dict(zip(FEATURES, feature_vector(last))),
        "dataset_hash": fingerprint,
        "feature_version": manifest.get("feature_version", "legacy-v1") if manifest else "legacy-v1",
        "provenance": provenance,
        "validation_status": "OK" if provenance.get("validated") is True else "UNVERIFIED_PROVENANCE",
        # Uzun süredir değişmeyen girdiler tahmin edilen dönem hakkında bilgi
        # taşımaz; tahmin anında nötrlenmeleri için bildiriliyor.
        "frozen": list(frozen_features(rows, MACRO_FEATURES)),
    }
