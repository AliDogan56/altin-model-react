"""Gün içi akış yedeği: vadeli akış susunca spot izleyen seriye düşme.

Ölçüldü (2026-09-07, ABD İşçi Bayramı): vadeli akışın son mumu cuma 20:55 UTC,
58 saat boyunca yeni mum yok; momentum kartı cuma seansında donup kaldı.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.services import market_data_service as mds
from app.services.market_data_service import MarketDataService

NOW = datetime(2026, 9, 7, 6, 50, tzinfo=timezone.utc)


def yahoo(last: datetime, n: int = 30, price: float = 4476.0) -> dict:
    """`n` adet 5 dk mum, sonuncusu `last`'ta biten Yahoo gövdesi."""
    stamps = [int((last - timedelta(minutes=5 * (n - 1 - i))).timestamp()) for i in range(n)]
    closes = [price + i * 0.1 for i in range(n)]
    return {"chart": {"result": [{"timestamp": stamps, "indicators": {"quote": [{
        "open": closes, "high": [c + 1 for c in closes], "low": [c - 1 for c in closes], "close": closes,
        "volume": [10] * n}]}}]}}


def servis(by_key: dict):
    """`_get` anahtarına göre yanıt: dict döner, Exception fırlatır, yoksa test hatası."""
    service = MarketDataService()
    calls = []

    async def sahte(key, url, ttl, *, as_text=False):
        calls.append(key)
        if key not in by_key:
            raise AssertionError(f"beklenmeyen kaynak çağrısı: {key}")
        value = by_key[key]
        if isinstance(value, Exception):
            raise value
        return value

    service._get = sahte  # type: ignore[method-assign]
    return service, calls


def test_birincil_tazeyse_yedege_hic_bakilmaz():
    svc, calls = servis({"xau-intraday": yahoo(NOW - timedelta(minutes=5))})
    out = asyncio.run(svc.xau_intraday(now=NOW))
    assert out["source"] == mds.INTRADAY_SOURCE and out["fallback"] is False and out["fallback_reason"] is None
    assert out["stale"] is False and out["primary_age_minutes"] == 5 and out["count"] == 30
    assert calls == ["xau-intraday"]


def test_60_dakika_sinirda_taze_61_dakikada_yedek():
    tam = servis({"xau-intraday": yahoo(NOW - timedelta(minutes=60))})[0]
    assert asyncio.run(tam.xau_intraday(now=NOW))["fallback"] is False
    svc, calls = servis({"xau-intraday": yahoo(NOW - timedelta(minutes=61)),
                         "xau-intraday-fallback": yahoo(NOW - timedelta(minutes=3), price=4400.0)})
    out = asyncio.run(svc.xau_intraday(now=NOW))
    assert out["fallback"] is True and out["fallback_reason"] == "primary_stale"
    assert out["source"] == mds.INTRADAY_FALLBACK_SOURCE and out["bars"][-1]["c"] == pytest.approx(4402.9)
    assert out["primary_as_of"] == (NOW - timedelta(minutes=61)).isoformat() and out["primary_age_minutes"] == 61
    assert out["stale"] is False and calls == ["xau-intraday", "xau-intraday-fallback"]


def test_tatil_senaryosu_58_saat_sessiz_vadeli():
    cuma = datetime(2026, 9, 4, 20, 55, tzinfo=timezone.utc)
    svc, _ = servis({"xau-intraday": yahoo(cuma), "xau-intraday-fallback": yahoo(NOW - timedelta(minutes=4), price=4395.0)})
    out = asyncio.run(svc.xau_intraday(now=NOW))
    assert out["fallback"] is True and out["primary_age_minutes"] == 58 * 60 - 5
    assert out["bars"][-1]["t"] == (NOW - timedelta(minutes=4)).isoformat()


def test_yedek_daha_taze_degilse_birincil_kalir():
    svc, _ = servis({"xau-intraday": yahoo(NOW - timedelta(hours=3)),
                     "xau-intraday-fallback": yahoo(NOW - timedelta(hours=4))})
    out = asyncio.run(svc.xau_intraday(now=NOW))
    assert out["fallback"] is False and out["source"] == mds.INTRADAY_SOURCE and out["stale"] is True


def test_birincil_bayat_yedek_alinamazsa_birincil_bayat_etiketiyle_doner(caplog):
    svc, _ = servis({"xau-intraday": yahoo(NOW - timedelta(hours=3)),
                     "xau-intraday-fallback": httpx.ConnectError("yedek yok")})
    out = asyncio.run(svc.xau_intraday(now=NOW))
    assert out["fallback"] is False and out["stale"] is True and out["primary_age_minutes"] == 180
    assert any("yedek kaynak alınamadı" in m for m in caplog.messages)


def test_birincil_alinamazsa_yedek_devreye_girer():
    svc, calls = servis({"xau-intraday": httpx.ConnectError("vadeli yok"),
                         "xau-intraday-fallback": yahoo(NOW - timedelta(minutes=2), price=4400.0)})
    out = asyncio.run(svc.xau_intraday(now=NOW))
    assert out["fallback"] is True and out["fallback_reason"] == "primary_unavailable"
    assert out["primary_as_of"] is None and out["primary_age_minutes"] is None
    assert calls == ["xau-intraday", "xau-intraday-fallback"]


def test_birincil_200_ile_bos_govde_de_yedege_dusurur():
    svc, _ = servis({"xau-intraday": {"chart": {"result": []}},
                     "xau-intraday-fallback": yahoo(NOW - timedelta(minutes=2))})
    assert asyncio.run(svc.xau_intraday(now=NOW))["fallback"] is True


def test_ikisi_de_yoksa_birincilin_hatasi_yukselir():
    svc, _ = servis({"xau-intraday": httpx.ConnectError("vadeli yok"),
                     "xau-intraday-fallback": httpx.ConnectError("yedek yok")})
    with pytest.raises(httpx.ConnectError, match="vadeli yok"):
        asyncio.run(svc.xau_intraday(now=NOW))


def test_momentum_ucu_feed_blogunu_tasir(monkeypatch):
    """Eski gövde korunur; `feed` yeni ve ek bir anahtardır."""
    from fastapi.testclient import TestClient
    from app.main import app

    async def sahte_intraday(*, now=None):
        return {"symbol": "XAUUSD", "interval": "5m", "source": mds.INTRADAY_FALLBACK_SOURCE,
                "bars": mds.yahoo_to_bars(yahoo(NOW - timedelta(minutes=2), n=200)), "count": 200,
                "fallback": True, "fallback_reason": "primary_stale",
                "primary_as_of": "2026-09-04T20:55:00+00:00", "primary_age_minutes": 3475, "stale": False}

    async def sahte_history():
        return {"points": []}

    monkeypatch.setattr(mds.market_data_service, "xau_intraday", sahte_intraday)
    monkeypatch.setattr(mds.market_data_service, "xau_history", sahte_history)
    body = TestClient(app).get("/v1/market/xau/momentum").json()
    assert body["feed"] == {"source": "yahoo:PAXG-USD", "fallback": True, "reason": "primary_stale",
                            "primary_as_of": "2026-09-04T20:55:00+00:00", "primary_age_minutes": 3475, "stale": False}
    assert {"as_of", "direction", "strength", "components", "session"} <= set(body)
