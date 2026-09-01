"""Donmuş girdi nötrlenince tahmin gerçekten değişmeli.

2026-08-31 ölçümü: `core_cpi_yoy` 20 işlem günüdür sabitti ve 30 günlük
tahminin +%3,54'ünün +3,02 puanını tek başına taşıyordu.
"""
import numpy as np
import pytest

from app.services.model_service import ModelService
from app.services.xau_dataset_service import FEATURES


class SahteAg:
    """Tek bir girdiye bağlı doğrusal ağ: nötrlemenin etkisi kesin hesaplanır."""

    def __init__(self, index, katsayi):
        self.index, self.katsayi = index, katsayi

    def predict(self, x):
        return np.asarray([x[0][self.index] * self.katsayi])


@pytest.fixture
def servis():
    hedef = FEATURES.index("core_cpi_yoy")
    service = ModelService()
    service.version = "test"
    # `horizons` koddan gelir (7/14/30); artefakt hepsini taşımalı.
    durum = lambda: {
        "x_mean": np.zeros(len(FEATURES)), "x_std": np.ones(len(FEATURES)),
        "networks": [SahteAg(hedef, 0.01)], "weight": 1.0,
        "error80": 0.05, "training_volatility": 0.2,
    }
    service.active = {
        "version": "test", "features": list(FEATURES), "horizons": list(service.horizons),
        "per_horizon": {h: durum() for h in service.horizons},
    }
    return service


def girdiler(**ozel):
    base = {name: 0.0 for name in FEATURES}
    base.update(ozel)
    return base


def test_notrlenmeyince_girdi_tahmini_suruklyor(servis):
    out = servis.predict(girdiler(core_cpi_yoy=3.0), 4500.0)
    assert out["mean"][0] == pytest.approx(0.03)
    assert out["neutralized_features"] == []


def test_notrlenince_katkisi_sifirlanir(servis):
    out = servis.predict(girdiler(core_cpi_yoy=3.0), 4500.0, ("core_cpi_yoy",))
    assert out["mean"][0] == pytest.approx(0.0)
    assert out["neutralized_features"] == ["core_cpi_yoy"]


def test_bilinmeyen_ad_yok_sayilir(servis):
    out = servis.predict(girdiler(core_cpi_yoy=3.0), 4500.0, ("olmayan_girdi",))
    assert out["mean"][0] == pytest.approx(0.03)
    assert out["neutralized_features"] == []


def test_notrleme_diger_girdileri_bozmaz(servis):
    # Yalnız adı verilen girdi sıfırlanmalı; ağ başka girdiye bakıyorsa etkilenmemeli.
    for h in servis.horizons:
        servis.active["per_horizon"][h]["networks"] = [SahteAg(FEATURES.index("vix_level"), 0.01)]
    out = servis.predict(girdiler(vix_level=2.0), 4500.0, ("core_cpi_yoy",))
    assert out["mean"][0] == pytest.approx(0.02)


def test_notrlenen_girdi_yanitla_bildirilir(servis):
    out = servis.predict(girdiler(), 4500.0, ("core_cpi_yoy", "vix_level"))
    # Arayüz hangi girdinin hesaba katılmadığını yazabilsin diye sıralı liste.
    assert out["neutralized_features"] == ["core_cpi_yoy", "vix_level"]
