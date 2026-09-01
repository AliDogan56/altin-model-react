"""Veri seti üreticisi de birincil kaynağa bağımlı olmamalı.

2026-08-31'de xaus.com 503 vermeye başladı; saatlik job "HTTP Error 503" ile
düştü ve veri seti donup kaldı (`last_error` alanında görüldü).
"""
from datetime import date, datetime, time, timezone

import pytest

from app.services.xau_dataset_service import XauBar, fetch_bars, yahoo_bars


def epoch(iso: str) -> int:
    return int(datetime.combine(date.fromisoformat(iso), time.min, timezone.utc).timestamp())


YAHOO = {"chart": {"result": [{
    "timestamp": [epoch("2026-08-31"), epoch("2026-09-01"), epoch("2026-09-02")],
    "indicators": {"quote": [{
        "close": [4476.3, 4415.3, None],
        "high": [4520.0, 4510.5, None],
        "low": [4460.0, 4413.0, None],
    }]},
}]}}

PRIMARY = {"points": [{"d": "2026-08-31", "c": 4504.8, "h": 4530.0, "l": 4480.0}]}


class SahteYanit:
    def __init__(self, payload=None, hata=None):
        self._payload, self._hata = payload, hata

    def raise_for_status(self):
        if self._hata:
            raise self._hata

    def json(self):
        return self._payload


class SahteIstemci:
    """İlk çağrı birincil kaynağa, ikinci çağrı yedeğe gider."""

    def __init__(self, *yanitlar):
        self._kuyruk = list(yanitlar)
        self.cagrilan = []

    def get(self, url, **kw):
        self.cagrilan.append(url)
        return self._kuyruk.pop(0)


def test_birincil_calisirken_yedege_gidilmez():
    istemci = SahteIstemci(SahteYanit(PRIMARY))
    bars = fetch_bars(istemci)
    assert len(bars) == 1
    assert bars[0].close == 4504.8
    assert len(istemci.cagrilan) == 1


def test_birincil_dusunce_yedek_kullanilir():
    istemci = SahteIstemci(SahteYanit(hata=RuntimeError("503")), SahteYanit(YAHOO))
    bars = fetch_bars(istemci)
    assert [bar.day.isoformat() for bar in bars] == ["2026-08-31", "2026-09-01"]
    assert len(istemci.cagrilan) == 2


def test_yedek_de_dusesse_hata_yukselir():
    istemci = SahteIstemci(SahteYanit(hata=RuntimeError("503")), SahteYanit(hata=RuntimeError("503")))
    with pytest.raises(RuntimeError):
        fetch_bars(istemci)


def test_eksik_gunler_atlanir():
    assert len(yahoo_bars(YAHOO)) == 2


def test_barlar_tarih_sirali():
    karisik = {"chart": {"result": [{
        "timestamp": [epoch("2026-09-01"), epoch("2026-08-31")],
        "indicators": {"quote": [{"close": [2, 1], "high": [2, 1], "low": [2, 1]}]},
    }]}}
    assert [b.day.isoformat() for b in yahoo_bars(karisik)] == ["2026-08-31", "2026-09-01"]


def test_bar_alanlari_dogru_esleniyor():
    bar = yahoo_bars(YAHOO)[0]
    assert isinstance(bar, XauBar)
    assert (bar.high, bar.low, bar.close) == (4520.0, 4460.0, 4476.3)


@pytest.mark.parametrize("bozuk", [
    {}, {"chart": {}}, {"chart": {"result": []}},
    {"chart": {"result": [{"timestamp": [], "indicators": {"quote": [{}]}}]}},
])
def test_bozuk_yedek_govdesi_reddedilir(bozuk):
    with pytest.raises(ValueError):
        yahoo_bars(bozuk)
