"""`technical/session.py` — taşınan gün içi momentum bloğunun bit-bit sabitlenmesi.

`momentum_service.py` 2026-09-06'da `technical/session.py`'ye taşındı; matematik
değişmedi. Bu dosya bunu ölçümle kanıtlar: aynı gün canlıdan alınan yanıt
(`momentum_live_20260906.json`) ile aynı girdilerden (`intraday_20260906.json`,
`xau_daily_20260906.json`) yerel yeniden hesap 0 farkla eşleşmişti. Burada o
eşitlik, denetleyicinin çağrı yoluyla birebir tekrarlanır.

Meşru olarak farklılaşabilecek bir alan yok: `as_of` son mumun zaman damgasıdır,
hesap anının değil. Bu yüzden hiçbir alan dışlanmadan **tam derin eşitlik** istenir.
Formül ya da sabit değişirse bu dosya kırılır; niyet de tam olarak budur.
"""
import json
from pathlib import Path

import pytest

from app.services import momentum_service as shim
from app.services.technical import session

FIXTURES = Path(__file__).parent / "fixtures"

# Eski testlerin ve denetleyicinin şim üzerinden kullandığı adlar; şim bunları
# `technical.session`'daki nesnelerin **kendisi** olarak vermeli.
KULLANILAN_ADLAR = (
    "MIN_BARS", "cluster_levels", "daily_pivots", "last_complete_week",
    "macd_histogram", "momentum", "nearest_levels", "rsi",
    "_complete_days", "session_drift",
)


def _yukle(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def girdiler():
    return _yukle("intraday_20260906.json"), _yukle("xau_daily_20260906.json")


@pytest.fixture(scope="module")
def canli():
    return _yukle("momentum_live_20260906.json")


def _denetleyici_gibi(intraday: dict, daily: dict) -> dict:
    """`market_controller.xau_momentum` ile aynı çağrı yolu.

    Denetleyici gün içi yanıtın `bars` listesini ve günlük yanıtın `points`
    listesini olduğu gibi geçirir; arada ayrı bir ayrıştırma adımı yoktur
    (`parse_bars` fonksiyonun içinde çalışır).
    """
    return session.momentum(intraday["bars"], daily=daily.get("points", []))


def test_fixture_girdileri_denetleyicinin_gordugu_sekilde():
    """Fixture'lar servis yanıtlarının kendisi: `bars` ve `points` listeleri."""
    intraday, daily = _yukle("intraday_20260906.json"), _yukle("xau_daily_20260906.json")
    assert intraday["count"] == len(intraday["bars"]) == 1034
    assert set(intraday["bars"][0]) == {"t", "o", "h", "l", "c", "v"}
    assert daily["count"] == len(daily["points"]) == 1257
    assert set(daily["points"][0]) == {"d", "c", "h", "l"}


def test_canli_yanitla_bit_bit_esit(girdiler, canli):
    """2026-09-06 canlı yanıtı ile yerel yeniden hesap: 0 fark."""
    assert _denetleyici_gibi(*girdiler) == canli


def test_json_gidis_donusu_sonrasi_da_esit(girdiler, canli):
    """Tel üzerinde giden şey JSON; float'lar yeniden yüklendiğinde de eşit kalmalı."""
    assert json.loads(json.dumps(_denetleyici_gibi(*girdiler))) == canli


def test_deterministik(girdiler):
    """Aynı girdi iki kez → aynı çıktı (gizli durum, rastgelelik, saat yok)."""
    assert _denetleyici_gibi(*girdiler) == _denetleyici_gibi(*girdiler)


def test_sim_seans_moduluyle_ayni_adlari_verir():
    """`momentum_service` şimi `technical.session`'ın her adını aynı nesne olarak verir."""
    def acik(mod):
        return {name for name in dir(mod) if not name.startswith("_")}

    assert acik(shim) == acik(session)
    for name in dir(session):
        if name.startswith("__"):
            continue
        assert getattr(shim, name) is getattr(session, name), name
    for name in KULLANILAN_ADLAR:
        assert getattr(shim, name) is getattr(session, name), name


def test_denetleyici_hala_ayni_fonksiyonu_cagiriyor():
    """`/xau/momentum` artık `technical_service.momentum_alias` üzerinden gider:
    normal yol `assemble.analyze` → `session.momentum`, günlük seri alınamayınca
    doğrudan `session.momentum`. İki yolda da çözümlenen nesne seans modülünün
    kendisi; şim (`momentum_service`) denetleyicide artık içe aktarılmıyor."""
    from app.controllers import market_controller
    from app.services import technical_service
    from app.services.technical import assemble
    assert assemble.session_block is session and assemble.session_block.momentum is session.momentum
    assert technical_service.session is session
    assert market_controller.technical_service.__class__ is technical_service.TechnicalService
    assert not hasattr(market_controller, "momentum")
