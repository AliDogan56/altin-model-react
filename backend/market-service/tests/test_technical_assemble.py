"""Uçtan uca: ham servis yükleri → analiz → DTO. Taban çizgisi 2026-09-06."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.technical import assemble
from app.services.technical.config import TechnicalConfig
from app.services.technical.pivots import PivotMethod, PivotPeriod

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 9, 6, 10, 2, 5, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def payloads():
    daily = json.loads((FIX / "xau_daily_20260906.json").read_text())
    intraday = json.loads((FIX / "intraday_20260906.json").read_text())
    return daily, intraday


@pytest.fixture(scope="module")
def analysis(payloads):
    return assemble.analyze(payloads[0], payloads[1], now=NOW)


@pytest.fixture(scope="module")
def dto(analysis):
    return assemble.to_dict(analysis)


def test_referans_ve_gunluk_hareket(analysis):
    assert analysis.reference.value == 4476.6 and analysis.reference.frame == "intraday_close"
    ch = analysis.daily_change
    assert ch["close"] == 4476.6 and ch["previous_close"] == 4491.7
    assert round(ch["usd"], 2) == -15.1 and round(ch["pct"], 4) == -0.0034


def test_tum_bloklar_ok(analysis):
    assert analysis.status == {"daily": "OK", "session": "OK", "indicators": "OK", "pivots": "OK", "levels": "OK",
                               "momentum_daily": "OK", "breakout": "OK", "trend": "OK"}


def test_seans_blogu_canli_yanitla_ayni(analysis):
    live = json.loads((FIX / "momentum_live_20260906.json").read_text())
    assert analysis.session == live
    assert analysis.market_state == "CLOSED" and str(analysis.session_date) == "2026-09-04" and not analysis.session_stale


def test_gostergeler_ve_atr(analysis):
    assert round(analysis.atr, 2) == 86.66
    assert set(analysis.indicators) >= {"rsi", "atr", "adx", "macd"}
    assert len(analysis.moving_averages) == 6


def test_baslik_merdiveni_haftalik_klasik(analysis):
    chosen, ladder = assemble.headline(analysis, PivotMethod.CLASSIC, PivotPeriod.WEEKLY)
    assert chosen.period_id == "2026-08-31" and chosen.status == "OK"
    assert dict(chosen.levels)["P"] == pytest.approx(4435.5333, abs=1e-3)
    assert (ladder.nearest_up, ladder.nearest_down, ladder.testing) == ("R1", "P", ())
    assert ladder.price == 4476.6 and ladder.margin_usd > 0


def test_pivot_setleri_27(analysis):
    assert set(analysis.pivot_sets) == {PivotPeriod.DAILY, PivotPeriod.WEEKLY, PivotPeriod.MONTHLY}
    assert all(set(m) == {PivotMethod.CLASSIC, PivotMethod.FIBONACCI, PivotMethod.CAMARILLA} for m in analysis.pivot_sets.values())


def test_bolgeler_ve_kirilim(analysis):
    lv = analysis.levels
    assert lv.zones and lv.nearest_support and lv.nearest_resistance
    assert analysis.breakout.up.status == "OK" and analysis.breakout.down.status == "OK"
    assert analysis.breakout.note == "NOT_A_PROBABILITY"
    assert analysis.momentum_daily.score is not None and analysis.momentum_daily.status == "OK"


def test_trend_bes_aralik(analysis):
    assert set(analysis.trend) == {"gunluk", "haftalik", "aylik", "ceyreklik", "yarim"}
    assert analysis.trend["gunluk"].fit.direction == "DOWN"


def test_dto_json_serilestirilebilir_ve_sekil(dto):
    text = json.dumps(dto)
    assert len(text) < 400_000
    assert dto["version"] == "technical-v1" and len(dto["config_hash"]) == 12
    assert dto["reference"]["note"] == "LIVE_QUOTE_NOT_USED" and dto["reference"]["source"]["daily_fallback"] is False
    assert dto["daily"]["body_definition"] == "prev_close_to_close" and dto["daily"]["quality"]["zero_range"] == 55
    assert dto["daily"]["candles"][-1][0] == "2026-09-04" and dto["daily"]["candles"][-1][4] == 4491.7
    assert dto["pivots"]["headline"]["ladder"]["nearest_up"] == "R1"
    assert set(dto["pivots"]["sets"]) == {"daily", "weekly", "monthly"} and "camarilla" in dto["pivots"]["sets"]["weekly"]
    assert dto["session"]["strength"] == 22 and dto["session"]["market_state"] == "CLOSED"
    assert dto["breakout"]["up"]["strength"] is not None and dto["breakout"]["down"]["label"] in ("WEAK", "MODERATE", "STRONG")
    assert dto["trend"]["ranges"]["gunluk"]["rows"] and "b1" in dto["trend"]["ranges"]["gunluk"]["rows"][0]


def test_dto_include_alt_kumesi(analysis):
    small = assemble.to_dict(analysis, include=["pivots", "breakout"])
    assert set(small) == {"version", "generated_at", "config_hash", "meta", "status", "reference", "pivots", "breakout"}
    with pytest.raises(ValueError):
        assemble.to_dict(analysis, include=["yok"])


def test_kamarilla_baslik(analysis):
    d = assemble.to_dict(analysis, pivot_method=PivotMethod.CAMARILLA, pivot_period=PivotPeriod.DAILY, include=["pivots"])
    assert d["pivots"]["pivot_method"] == "CAMARILLA" and d["pivots"]["pivot_period"] == "DAILY"
    assert len(d["pivots"]["headline"]["ladder"]["items"]) == 9


def test_deterministik_ve_hizli(payloads):
    t = time.perf_counter()
    a = assemble.to_dict(assemble.analyze(payloads[0], payloads[1], now=NOW))
    elapsed = time.perf_counter() - t
    b = assemble.to_dict(assemble.analyze(payloads[0], payloads[1], now=NOW))
    assert a == b
    assert elapsed < 1.0, elapsed  # hedef 250 ms; CI dalgalanması için gevşek üst sınır


def test_gun_ici_yoksa_gunluk_cerceve(payloads):
    a = assemble.analyze(payloads[0], None, now=NOW)
    assert a.reference.frame == "daily_close" and a.status["session"] == "INTRADAY_UNAVAILABLE"
    assert a.breakout.expected_move_frame == "next_daily_bar" and a.breakout.up.status == "OK"
    assert assemble.to_dict(a)["session"]["status"] == "INTRADAY_UNAVAILABLE"


def test_gun_ici_kisa_ise_seans_durumu(payloads):
    short = {**payloads[1], "bars": payloads[1]["bars"][-20:]}
    a = assemble.analyze(payloads[0], short, now=NOW)
    assert a.status["session"] == "SESSION_TOO_SHORT" and a.session is None
    assert a.breakout is not None and a.breakout.expected_move_frame == "next_daily_bar"


def test_bos_ve_yetersiz_gunluk(payloads):
    empty = assemble.analyze({"points": []}, None, now=NOW)
    assert empty.status["daily"] == "NO_DATA" and empty.reference.value is None
    assert all(v != "OK" for v in empty.status.values())
    assert json.dumps(assemble.to_dict(empty))
    few = assemble.analyze({"points": payloads[0]["points"][-20:]}, None, now=NOW)
    assert few.status["daily"] == "OK" and few.status["indicators"] == "INSUFFICIENT_DATA"
    assert few.daily_change is not None and few.status["levels"] == "INSUFFICIENT_DATA"


def test_duz_piyasa(payloads):
    flat = {"points": [{"d": p["d"], "c": 100.0, "h": 100.0, "l": 100.0} for p in payloads[0]["points"][-120:]]}
    a = assemble.analyze(flat, None, now=NOW)
    assert a.status["levels"] == "FLAT_MARKET" and a.status["momentum_daily"] == "FLAT_MARKET"
    assert a.status["breakout"] == "FLAT_MARKET"


def test_olusan_gun_atilir(payloads):
    pts = payloads[0]["points"] + [{"d": "2026-09-06", "c": 4500, "h": 4510, "l": 4490}]
    a = assemble.analyze({**payloads[0], "points": pts}, None, now=NOW)
    assert a.last_is_forming and a.daily[-1].date.isoformat() == "2026-09-04"


def test_config_hash_dto_ya_yansir(payloads):
    cfg = TechnicalConfig.from_env({"TA_LEVELS_MIN_STRENGTH": "45"})
    a = assemble.analyze(payloads[0], payloads[1], now=NOW, cfg=cfg)
    assert a.config_hash == cfg.config_hash() != TechnicalConfig().config_hash()
    assert a.levels.min_strength == 45
