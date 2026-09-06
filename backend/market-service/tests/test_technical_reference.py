import json
from datetime import date, datetime, timezone
from pathlib import Path

from app.services.technical.candles import Candle, IntradayBar, normalize_daily, normalize_intraday
from app.services.technical.reference import (FRAME_DAILY, FRAME_INTRADAY, NOTE, STATUS_INTRADAY_STALE,
                                              STATUS_INTRADAY_UNAVAILABLE, STATUS_NO_DATA, STATUS_OK, choose_reference)

FIX = Path(__file__).parent / "fixtures"


def _daily(*closes, start=date(2026, 9, 1)):
    return [Candle(date(start.year, start.month, start.day + i), c + 1, c - 1, c) for i, c in enumerate(closes)]


def _bar(day, close, hour=20):
    t = datetime(2026, 9, day, hour, 0, tzinfo=timezone.utc)
    return IntradayBar(t, close, close + 1, close - 1, close, 10.0)


def test_gun_ici_var_ve_guncel_ise_gun_ici_kapanis():
    ref = choose_reference(_daily(100, 101, 102), [_bar(3, 105)])
    assert (ref.value, ref.frame, ref.status) == (105.0, FRAME_INTRADAY, STATUS_OK)
    assert ref.daily_close == 102.0 and ref.daily_date == date(2026, 9, 3)


def test_gun_ici_yoksa_gunluk_kapanis():
    ref = choose_reference(_daily(100, 101, 102), None)
    assert (ref.value, ref.frame, ref.status) == (102.0, FRAME_DAILY, STATUS_INTRADAY_UNAVAILABLE)
    assert ref.as_of == datetime(2026, 9, 3, tzinfo=timezone.utc)


def test_gun_ici_gunlukten_eskiyse_bayat():
    ref = choose_reference(_daily(100, 101, 102), [_bar(2, 999)])
    assert (ref.value, ref.frame, ref.status) == (102.0, FRAME_DAILY, STATUS_INTRADAY_STALE)


def test_bos_gunluk_seri():
    ref = choose_reference([], [_bar(3, 105)])
    assert ref.status == STATUS_NO_DATA and ref.value is None


def test_harem_hic_okunmaz_notu():
    assert choose_reference(_daily(100), None).note == NOTE


def test_fixture_referans_4476_6():
    """2026-09-06 taban çizgisi: son 5 dk bar 2026-09-04 20:59 UTC, kapanış 4476.6."""
    daily, _ = normalize_daily(json.loads((FIX / "xau_daily_20260906.json").read_text())["points"])
    bars, _ = normalize_intraday(json.loads((FIX / "intraday_20260906.json").read_text())["bars"])
    ref = choose_reference(daily, bars)
    assert ref.value == 4476.6 and ref.frame == FRAME_INTRADAY and ref.status == STATUS_OK
    assert ref.daily_date == date(2026, 9, 4) and ref.as_of.isoformat() == "2026-09-04T20:59:58+00:00"
