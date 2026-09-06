"""`technical/cache.py` — tek giriş, tek uçuş, güvenlik TTL'i.

Saat enjekte edilir; hiçbir test gerçek zaman beklemez. `compute` sayacı
"kaç kez hesaplandı" sorusunun tek ölçüsüdür.
"""
import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.technical.cache import AnalysisCache, analysis_key

T0 = datetime(2026, 9, 6, 10, 0, tzinfo=timezone.utc)


class Saat:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now

    def ilerle(self, seconds):
        self.now += timedelta(seconds=seconds)


class Sayac:
    """Her çağrıda biraz bekleyen (gerçek hesap gibi döngüyü bırakan) sahte hesap."""

    def __init__(self, delay=0.01):
        self.calls = 0
        self.delay = delay

    async def __call__(self):
        self.calls += 1
        await asyncio.sleep(self.delay)
        return {"n": self.calls}


def test_bes_es_zamanli_soguk_istek_tek_hesap():
    cache = AnalysisCache(300, clock=Saat())
    hesap = Sayac()

    async def kosu():
        return await asyncio.gather(*(cache.get_or_compute("k1", hesap) for _ in range(5)))

    sonuc = asyncio.run(kosu())
    assert hesap.calls == 1
    assert [value for value, _ in sonuc] == [{"n": 1}] * 5
    assert sorted(meta["hit"] for _, meta in sonuc) == [False, True, True, True, True]
    assert {meta["cache_key"] for _, meta in sonuc} == {"k1"}
    assert cache.pending_keys() == ()  # kilit sözlüğü bekleyen kalmayınca boşalır


def test_ayni_anahtar_ikinci_istek_onbellekten():
    cache = AnalysisCache(300, clock=Saat())
    hesap = Sayac()
    a, ma = asyncio.run(cache.get_or_compute("k1", hesap))
    b, mb = asyncio.run(cache.get_or_compute("k1", hesap))
    assert hesap.calls == 1 and a is b
    assert (ma["hit"], mb["hit"]) == (False, True)
    assert ma["computed_at"] == mb["computed_at"] == "2026-09-06T10:00:00Z"


def test_anahtar_degisince_yeniden_hesap_ve_eski_giris_atilir():
    cache = AnalysisCache(300, clock=Saat())
    hesap = Sayac()
    asyncio.run(cache.get_or_compute("k1", hesap))
    _, meta = asyncio.run(cache.get_or_compute("k2", hesap))
    assert hesap.calls == 2 and meta["hit"] is False
    assert cache.entry.key == "k2"
    # Tek giriş: k1 artık yok, tekrar sorulursa yeniden hesaplanır.
    _, meta = asyncio.run(cache.get_or_compute("k1", hesap))
    assert hesap.calls == 3 and meta["hit"] is False and cache.entry.key == "k1"


def test_ttl_dolunca_ayni_anahtarla_bile_yeniden_hesap():
    saat = Saat()
    cache = AnalysisCache(300, clock=saat)
    hesap = Sayac()
    asyncio.run(cache.get_or_compute("k1", hesap))
    saat.ilerle(299)
    _, meta = asyncio.run(cache.get_or_compute("k1", hesap))
    assert hesap.calls == 1 and meta["hit"] is True
    saat.ilerle(1)  # tam 300 sn: artık taze değil
    _, meta = asyncio.run(cache.get_or_compute("k1", hesap))
    assert hesap.calls == 2 and meta["hit"] is False
    assert meta["computed_at"] == "2026-09-06T10:05:00Z"


def test_ttl_sifir_onbellegi_kapatir():
    cache = AnalysisCache(0, clock=Saat())
    hesap = Sayac()
    asyncio.run(cache.get_or_compute("k1", hesap))
    asyncio.run(cache.get_or_compute("k1", hesap))
    assert hesap.calls == 2


def test_hesap_hata_verirse_giris_yazilmaz_kilit_kalmaz():
    cache = AnalysisCache(300, clock=Saat())
    calls = 0

    async def patlayan():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("kaynak yok")
        return "ok"

    with pytest.raises(RuntimeError):
        asyncio.run(cache.get_or_compute("k1", patlayan))
    assert cache.entry is None and cache.pending_keys() == ()
    value, meta = asyncio.run(cache.get_or_compute("k1", patlayan))
    assert value == "ok" and meta["hit"] is False


def test_farkli_anahtarlar_birbirini_beklemez():
    """Geçiş anında yeni anahtarlı istek eski anahtarın hesabını beklemek zorunda değil."""
    cache = AnalysisCache(300, clock=Saat())
    sira = []

    async def yavas():
        sira.append("yavas-basladi")
        await asyncio.sleep(0.05)
        sira.append("yavas-bitti")
        return "a"

    async def hizli():
        sira.append("hizli")
        return "b"

    async def kosu():
        t1 = asyncio.create_task(cache.get_or_compute("k1", yavas))
        await asyncio.sleep(0.01)
        t2 = asyncio.create_task(cache.get_or_compute("k2", hizli))
        return await asyncio.gather(t1, t2)

    asyncio.run(kosu())
    assert sira == ["yavas-basladi", "hizli", "yavas-bitti"]


# --- anahtar ------------------------------------------------------------------

DAILY = {"points": [{"d": "2026-09-03", "c": 1}, {"d": "2026-09-04", "c": 2}], "source": "xaus.com"}
INTRA = {"bars": [{"t": "2026-09-04T20:55:00+00:00"}, {"t": "2026-09-04T20:59:58+00:00"}]}


def test_anahtar_alanlari_sirali():
    key = analysis_key(DAILY, INTRA, today=date(2026, 9, 6), config_hash="abc123")
    assert key == "2026-09-04|2|xaus.com|0|2026-09-04T20:59:58+00:00|2|2026-09-06|abc123"


def test_gun_ici_yokken_anahtar_none_ve_sifir():
    key = analysis_key(DAILY, None, today=date(2026, 9, 6), config_hash="abc123")
    assert key == "2026-09-04|2|xaus.com|0||0|2026-09-06|abc123"
    assert analysis_key(DAILY, {"bars": []}, today=date(2026, 9, 6), config_hash="abc123") == key


def test_yedek_kaynak_ve_gun_anahtari_degistirir():
    base = analysis_key(DAILY, INTRA, today=date(2026, 9, 6), config_hash="abc123")
    fallback = analysis_key({**DAILY, "source": "yahoo:GC=F", "fallback": True}, INTRA,
                            today=date(2026, 9, 6), config_hash="abc123")
    ertesi = analysis_key(DAILY, INTRA, today=date(2026, 9, 7), config_hash="abc123")
    cfg = analysis_key(DAILY, INTRA, today=date(2026, 9, 6), config_hash="def456")
    assert len({base, fallback, ertesi, cfg}) == 4
    assert "|yahoo:GC=F|1|" in fallback


def test_anahtar_etag_icin_gecerli_karakterlerden_olusur():
    """Boşluk ve tırnak ETag'de geçersiz; kaynak adı böyle gelirse indirgenir."""
    key = analysis_key({**DAILY, "source": 'yahoo finance "GC=F"'}, INTRA, today=date(2026, 9, 6), config_hash="x")
    assert '"' not in key and " " not in key
    assert "yahoo_finance__GC=F_" in key
    assert all(0x21 <= ord(ch) <= 0x7E and ch != '"' for ch in key)
