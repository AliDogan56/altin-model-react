"""`GET /v1/market/xau/technical` ve eski `GET /v1/market/xau/momentum` takma adı.

Veri kaynağı 2026-09-06 fixture'larıyla değiştirilir, saat o güne dondurulur.
Servisin saati dondurulmasa günlük serinin "oluşan gün" kesimi ve dönem
tamamlanma kuralı testin koşulduğu güne göre kayardı.
"""
import gzip
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.controllers import market_controller
from app.main import app
from app.services.market_data_service import market_data_service
from app.services.technical.assemble import BLOCKS
from app.services.technical_service import TechnicalService

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 9, 6, 10, 2, 5, tzinfo=timezone.utc)
TECHNICAL = "/v1/market/xau/technical"
MOMENTUM = "/v1/market/xau/momentum"
# Eski denetleyicinin `momentum()` ValueError'ını 503'e çevirirken kullandığı metin.
ESKI_503_METNI = "Momentum için en az 47 gün içi mum gerekli; 20 geldi"


@pytest.fixture(scope="module")
def daily():
    return json.loads((FIX / "xau_daily_20260906.json").read_text())


@pytest.fixture(scope="module")
def intraday():
    return json.loads((FIX / "intraday_20260906.json").read_text())


@pytest.fixture(scope="module")
def live_momentum():
    return json.loads((FIX / "momentum_live_20260906.json").read_text())


@pytest.fixture
def kaynak(monkeypatch, daily, intraday):
    """Veri kaynağını fixture'lara bağlar; testler `.daily/.intraday` ile değiştirir."""
    class Kaynak:
        def __init__(self):
            self.daily = daily
            self.intraday = intraday
            self.daily_calls = 0
            self.intraday_calls = 0

        async def xau_history(self):
            self.daily_calls += 1
            if isinstance(self.daily, Exception):
                raise self.daily
            return self.daily

        async def xau_intraday(self):
            self.intraday_calls += 1
            if isinstance(self.intraday, Exception):
                raise self.intraday
            return self.intraday

    k = Kaynak()
    monkeypatch.setattr(market_data_service, "xau_history", k.xau_history)
    monkeypatch.setattr(market_data_service, "xau_intraday", k.xau_intraday)
    # Her test taze bir servis (boş önbellek) ve dondurulmuş saatle başlar.
    monkeypatch.setattr(market_controller, "technical_service", TechnicalService(market_data_service, clock=lambda: NOW))
    return k


@pytest.fixture
def client(kaynak):
    # Bağlam yöneticisi kullanılmaz: startup kancası SQLite dosyası açıyor, teste gerekmiyor.
    return TestClient(app)


# --- /xau/technical -----------------------------------------------------------

def test_tum_bloklar_200_ve_basliklar(client):
    r = client.get(TECHNICAL)
    assert r.status_code == 200
    body = r.json()
    assert set(BLOCKS) <= set(body)
    assert body["meta"]["blocks"] == sorted(BLOCKS)
    assert all(v == "OK" for v in body["status"].values()), body["status"]
    assert body["reference"]["value"] == 4476.6 and body["reference"]["frame"] == "intraday_close"
    cache = body["meta"]["cache"]
    assert cache["hit"] is False and cache["computed_at"] == "2026-09-06T10:02:05Z"
    assert cache["cache_key"] == "2026-09-04|1257|xaus.com|0|2026-09-04T20:59:58+00:00|1034|2026-09-06|" + body["config_hash"]
    assert r.headers["etag"] == f'"{cache["cache_key"]}"'   # RFC 7232: ETag tırnaklı
    assert r.headers["cache-control"] == "no-cache"
    assert len(r.content) < 400_000 and len(gzip.compress(r.content)) < 100_000


def test_ikinci_istek_onbellekten_ayni_etag(client, kaynak):
    a = client.get(TECHNICAL)
    b = client.get(TECHNICAL)
    assert a.json()["meta"]["cache"]["hit"] is False
    assert b.json()["meta"]["cache"]["hit"] is True
    assert a.headers["etag"] == b.headers["etag"]
    assert kaynak.daily_calls == 2 and kaynak.intraday_calls == 2  # anahtar için yük her seferinde okunur (servis önbelleği var)


def test_include_alt_kumesi(client):
    r = client.get(TECHNICAL, params={"include": "pivots,breakout"})
    assert r.status_code == 200
    assert set(r.json()) == {"version", "generated_at", "config_hash", "meta", "status", "reference", "pivots", "breakout"}
    assert r.json()["meta"]["blocks"] == ["breakout", "pivots"]
    # boşluk ve boş öge tolere edilir
    assert set(client.get(TECHNICAL, params={"include": " pivots , ,breakout "}).json()["meta"]["blocks"]) == {"pivots", "breakout"}


def test_kamarilla_gunluk_kucuk_harf_yansir(client):
    r = client.get(TECHNICAL, params={"pivot_method": "camarilla", "pivot_period": "daily", "include": "pivots"})
    assert r.status_code == 200
    p = r.json()["pivots"]
    assert (p["pivot_method"], p["pivot_period"]) == ("CAMARILLA", "DAILY")
    assert len(p["headline"]["ladder"]["items"]) == 9
    buyuk = client.get(TECHNICAL, params={"pivot_method": "CAMARILLA", "pivot_period": "DAILY", "include": "pivots"})
    assert buyuk.json()["pivots"] == p


def test_pivot_secimi_onbellek_anahtarini_degistirmez(client):
    """Başlık merdiveni istek anında kurulur; analiz aynı hesaptan gelir."""
    a = client.get(TECHNICAL, params={"pivot_method": "classic"})
    b = client.get(TECHNICAL, params={"pivot_method": "fibonacci"})
    assert a.headers["etag"] == b.headers["etag"]
    assert b.json()["meta"]["cache"]["hit"] is True
    assert a.json()["pivots"]["headline"]["method"] == "CLASSIC" and b.json()["pivots"]["headline"]["method"] == "FIBONACCI"


@pytest.mark.parametrize("params", [{"pivot_method": "woodie"}, {"pivot_period": "yearly"}, {"pivot_method": ""}])
def test_gecersiz_pivot_parametresi_422(client, params, kaynak):
    r = client.get(TECHNICAL, params=params)
    assert r.status_code == 422
    assert kaynak.daily_calls == 0  # doğrulama üst kaynağa dokunmadan


def test_gecersiz_include_422_ve_mesaj(client, kaynak):
    r = client.get(TECHNICAL, params={"include": "pivots,yok,abc"})
    assert r.status_code == 422
    assert r.json() == {"detail": "Bilinmeyen blok: abc, yok"}
    assert kaynak.daily_calls == 0


def test_gun_ici_alinamazsa_technical_gunluk_cerceveyle_200(client, kaynak, caplog):
    kaynak.intraday = httpx.ConnectError("yahoo yok")
    with caplog.at_level(logging.WARNING, logger="app.services.technical_service"):
        r = client.get(TECHNICAL)
    assert r.status_code == 200
    body = r.json()
    assert body["session"]["status"] == "INTRADAY_UNAVAILABLE"
    assert body["reference"]["frame"] == "daily_close" and body["reference"]["value"] == 4476.6
    assert body["status"]["pivots"] == "OK" and body["status"]["breakout"] == "OK"
    assert body["meta"]["cache"]["cache_key"].split("|")[4:6] == ["", "0"]
    assert any("yahoo yok" in m for m in caplog.messages)


def test_gunluk_alinamazsa_technical_502(client, kaynak):
    kaynak.daily = httpx.HTTPStatusError("503", request=None, response=None)
    r = client.get(TECHNICAL)
    assert r.status_code == 502
    assert r.json()["detail"].startswith("Harici veri kaynağına ulaşılamadı: ")


# --- /xau/momentum takma adı --------------------------------------------------

def test_momentum_takma_adi_eski_govdeyle_bit_bit_esit(client, live_momentum):
    r = client.get(MOMENTUM)
    assert r.status_code == 200
    assert r.json() == live_momentum
    assert r.headers["deprecation"] == "true"
    assert r.headers["link"] == '</v1/market/xau/technical>; rel="successor-version"'


def test_momentum_takma_adi_technical_seans_blogunun_ham_hali(client, live_momentum):
    """DTO'nun `session` bloğu durum alanları ekler; takma ad eklemez."""
    dto = client.get(TECHNICAL, params={"include": "session"}).json()["session"]
    assert set(dto) > set(live_momentum)
    assert {k: dto[k] for k in live_momentum} == live_momentum


def test_momentum_kisa_seans_503_eski_metin(client, kaynak, intraday):
    kaynak.intraday = {**intraday, "bars": intraday["bars"][-20:]}
    r = client.get(MOMENTUM)
    assert r.status_code == 503
    assert r.json() == {"detail": ESKI_503_METNI}
    assert r.headers["deprecation"] == "true" and "successor-version" in r.headers["link"]


def test_momentum_duz_seans_503(client, kaynak, intraday):
    kaynak.intraday = {**intraday, "bars": [{**b, "o": 4400.0, "h": 4400.0, "l": 4400.0, "c": 4400.0} for b in intraday["bars"]]}
    r = client.get(MOMENTUM)
    assert r.status_code == 503
    assert r.json() == {"detail": "Gün içi oynaklık sıfır; momentum hesaplanamaz"}


def test_momentum_gun_ici_alinamazsa_502_eski_davranis(client, kaynak):
    kaynak.intraday = httpx.ConnectError("yahoo yok")
    r = client.get(MOMENTUM)
    assert r.status_code == 502
    assert r.json() == {"detail": "Harici veri kaynağına ulaşılamadı: yahoo yok"}


def test_momentum_gunluk_alinamazsa_eskisi_gibi_devam_ve_loglar(client, kaynak, caplog):
    """Eski uç günlük seriyi çıplak `except:` ile yutup boş merdivenle devam ediyordu.
    Davranış korunur; fark hatanın artık loglanması."""
    kaynak.daily = httpx.HTTPStatusError("503", request=None, response=None)
    with caplog.at_level(logging.WARNING, logger="app.services.technical_service"):
        r = client.get(MOMENTUM)
    assert r.status_code == 200
    body = r.json()
    assert body["direction"] == "NEUTRAL" and body["price"] == 4476.6
    assert body["ladder"] and all(len(lv["sources"]) == 1 for lv in body["ladder"])  # merdiven yalnız gün içi akıştan
    assert any("Günlük altın serisi alınamadı" in m for m in caplog.messages)


def test_momentum_ve_technical_ayni_hesabi_paylasir(client, kaynak):
    client.get(MOMENTUM)
    r = client.get(TECHNICAL)
    assert r.json()["meta"]["cache"]["hit"] is True


# --- şema ---------------------------------------------------------------------

def test_openapi_her_iki_ucu_listeler():
    paths = app.openapi()["paths"]
    assert {TECHNICAL, MOMENTUM} <= set(paths)
    assert paths[MOMENTUM]["get"]["deprecated"] is True
    params = {p["name"]: p for p in paths[TECHNICAL]["get"]["parameters"]}
    assert set(params) == {"pivot_method", "pivot_period", "include"}
    assert set(params["pivot_method"]["schema"]["enum"]) == {"CLASSIC", "classic", "FIBONACCI", "fibonacci", "CAMARILLA", "camarilla"}
    assert set(params["pivot_period"]["schema"]["enum"]) == {"DAILY", "daily", "WEEKLY", "weekly", "MONTHLY", "monthly"}
