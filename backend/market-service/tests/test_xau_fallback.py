"""Birincil altın kaynağı düştüğünde uç cevapsız kalmamalı.

2026-08-31'de xaus.com bir saatten uzun 503 döndü; uç 502 verdi ve grafikteki
gerçekleşen seri tamamen kayboldu.
"""
import asyncio
from datetime import date, datetime, time, timezone

import httpx
import pytest


from app.services.market_data_service import MarketDataService, yahoo_to_points


def epoch(iso: str) -> int:
    """Yahoo damgaları UTC gün başlangıcıdır; testte tarihten türetiyoruz ki
    elle yazılan sayılar yanlış yıla düşmesin."""
    return int(datetime.combine(date.fromisoformat(iso), time.min, timezone.utc).timestamp())

YAHOO = {
    "chart": {"result": [{
        "timestamp": [epoch("2026-08-31"), epoch("2026-09-01"), epoch("2026-09-02")],
        "indicators": {"quote": [{
            "close": [4476.3, 4415.3, None],
            "high": [4520.0, 4510.5, None],
            "low": [4460.0, 4413.0, None],
        }]},
    }]}
}


def servis(yanitlar):
    """Sıradaki her `_get` çağrısında listeden bir öge döndüren servis."""
    service = MarketDataService()
    kuyruk = list(yanitlar)

    async def sahte(key, url, ttl, *, as_text=False):
        sonuc = kuyruk.pop(0)
        if isinstance(sonuc, Exception):
            raise sonuc
        return sonuc

    service._get = sahte
    return service


def test_birincil_calisirken_yedege_gidilmez():
    out = asyncio.run(servis([{"points": [{"d": "2026-08-31", "c": 1, "h": 2, "l": 0}]}]).xau_history())
    assert out["points"][0]["d"] == "2026-08-31"
    assert "fallback" not in out


def test_birincil_dusunce_yedek_kaynak_kullanilir():
    hata = httpx.HTTPStatusError("503", request=None, response=None)
    out = asyncio.run(servis([hata, YAHOO]).xau_history())
    assert out["fallback"] is True
    assert out["source"] == "yahoo:GC=F"
    assert [row["d"] for row in out["points"]] == ["2026-08-31", "2026-09-01"]


def test_yedek_de_dusesse_hata_yukselir():
    # İki kaynak da yoksa sessizce boş dönmek çağıranı yanıltırdı.
    hata = httpx.HTTPStatusError("503", request=None, response=None)
    with pytest.raises(httpx.HTTPError):
        asyncio.run(servis([hata, hata]).xau_history())


def test_eksik_gunler_atlanir():
    out = yahoo_to_points(YAHOO)
    assert len(out["points"]) == 2           # üçüncü gün boştu
    assert out["count"] == 2


def test_govde_birincil_kaynakla_ayni_alanlari_tasir():
    # Tüketiciler (grafik ve veri seti üreticisi) yalnız bu alanları okuyor.
    row = yahoo_to_points(YAHOO)["points"][0]
    assert sorted(row) == ["c", "d", "h", "l"]
    assert row == {"d": "2026-08-31", "c": 4476.3, "h": 4520.0, "l": 4460.0}


def test_gunler_tarih_sirasinda():
    karisik = {"chart": {"result": [{
        "timestamp": [epoch("2026-09-01"), epoch("2026-08-31")],
        "indicators": {"quote": [{"close": [2, 1], "high": [2, 1], "low": [2, 1]}]},
    }]}}
    assert [r["d"] for r in yahoo_to_points(karisik)["points"]] == ["2026-08-31", "2026-09-01"]


@pytest.mark.parametrize("bozuk", [
    {}, {"chart": {}}, {"chart": {"result": []}},
    {"chart": {"result": [{"timestamp": [], "indicators": {"quote": [{}]}}]}},
])
def test_bozuk_yedek_govdesi_reddedilir(bozuk):
    with pytest.raises(httpx.RequestError):
        yahoo_to_points(bozuk)
