"""Mum normalizasyonu ve dönem tamamlanma kuralı.

Kritik davranışlar: bozuk satır hata değil sayım üretir, oluşmakta olan dönem
asla dönmez, kapanış mumu eksikse hoşgörü dolana kadar dönem verilmez.
"""
import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.services.technical.candles import (
    Candle, CompletionParams, Timeframe, aggregate, normalize_daily, normalize_intraday,
    period_end, period_key, previous_completed_period,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def gunluk_satirlar() -> list[dict]:
    return json.loads((FIXTURES / "xau_daily_20260906.json").read_text())["points"]


@pytest.fixture(scope="module")
def gunici_satirlar() -> list[dict]:
    return json.loads((FIXTURES / "intraday_20260906.json").read_text())["bars"]


def satir(d: str, c: float, h: float | None = None, l: float | None = None) -> dict:
    return {"d": d, "c": c, "h": c if h is None else h, "l": c if l is None else l}


def hafta(pazartesi: date, *, cuma_var: bool = True) -> list[dict]:
    """Sentetik bir işlem haftası: pazartesi–cuma, isteğe bağlı cuma mumu."""
    gunler = 5 if cuma_var else 4
    return [satir((pazartesi + timedelta(days=i)).isoformat(), 100 + i, 110 + i, 90 + i)
            for i in range(gunler)]


# --- normalize_daily ---------------------------------------------------------------

def test_sirasiz_girdi_siralanir_ve_yinelenen_tarihte_son_kayit_kalir():
    rows = [satir("2026-09-03", 30), satir("2026-09-01", 10), satir("2026-09-02", 20),
            satir("2026-09-01", 11)]
    candles, quality = normalize_daily(rows)
    assert [c.date.isoformat() for c in candles] == ["2026-09-01", "2026-09-02", "2026-09-03"]
    assert candles[0].close == 11  # son kayıt kazandı
    assert quality.dropped_duplicate == 1 and quality.kept == 3 and quality.received == 4
    assert quality.status == "OK"


def test_bos_ve_gecersiz_satirlar_atilir_ve_sayilir():
    rows = [
        satir("2026-09-01", 10),
        {"d": "2026-09-02", "c": None, "h": 11, "l": 9},        # kapanış boş
        {"d": "2026-09-03", "c": "abc", "h": 11, "l": 9},       # sayı değil
        {"d": "2026-09-04", "c": -5, "h": 11, "l": 9},          # pozitif değil
        {"d": "2026-09-05", "c": float("nan"), "h": 11, "l": 9},
        {"d": "2026-09-06", "c": float("inf"), "h": 11, "l": 9},
        {"d": "bugün", "c": 10, "h": 11, "l": 9},               # tarih bozuk
        {"c": 10, "h": 11, "l": 9},                              # tarih yok
        "bu bir satır değil",
        satir("2026-09-07", 12),
    ]
    candles, quality = normalize_daily(rows)
    assert [c.close for c in candles] == [10, 12]
    assert quality.dropped_invalid == 8 and quality.kept == 2 and quality.received == 10


def test_kapanis_aralik_disindaysa_aralik_genisletilir_ve_sayilir():
    rows = [satir("2026-09-01", 120, 110, 90), satir("2026-09-02", 80, 110, 90),
            satir("2026-09-03", 100, 110, 90)]
    candles, quality = normalize_daily(rows)
    assert (candles[0].low, candles[0].high) == (90, 120)
    assert (candles[1].low, candles[1].high) == (80, 110)
    assert (candles[2].low, candles[2].high) == (90, 110)
    assert quality.range_widened == 2 and quality.dropped_invalid == 0


def test_metin_fiyatlar_ve_esit_yuksek_dusuk_kabul_edilir():
    candles, quality = normalize_daily([{"d": "2026-09-01", "c": "1795.9", "h": "1795.9", "l": "1795.9"},
                                        satir("2026-09-02", 1800)])
    assert candles[0].close == candles[0].high == candles[0].low == 1795.9
    assert candles[0].open is None and candles[0].volume is None
    assert candles[0].end_date is None and candles[0].bars == 1
    assert quality.status == "OK"


def test_yetersiz_ve_bos_veri_durumu():
    _, tek = normalize_daily([satir("2026-09-01", 10)])
    assert tek.status == "INSUFFICIENT_DATA" and tek.first_date == tek.last_date == date(2026, 9, 1)
    _, bos = normalize_daily([{"d": "2026-09-01", "c": None, "h": 1, "l": 1}])
    assert bos.status == "NO_DATA" and bos.first_date is None and bos.kept == 0
    _, gevsek = normalize_daily([satir("2026-09-01", 10)], minimum=1)
    assert gevsek.status == "OK"


def test_dizi_olmayan_girdi_typeerror():
    with pytest.raises(TypeError):
        normalize_daily({"d": "2026-09-01"})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        normalize_daily("2026-09-01")  # type: ignore[arg-type]


def test_fixture_1257_mum_kronolojik_ve_tekil(gunluk_satirlar):
    candles, quality = normalize_daily(gunluk_satirlar)
    assert len(candles) == 1257 == quality.kept == quality.received
    assert candles[0].date == date(2021, 9, 7) and candles[-1].date == date(2026, 9, 4)
    assert quality.first_date == date(2021, 9, 7) and quality.last_date == date(2026, 9, 4)
    assert all(a.date < b.date for a, b in zip(candles, candles[1:]))
    assert quality.dropped_invalid == quality.dropped_duplicate == quality.range_widened == 0
    # 55 satırda h == l: bunlar veridir, atılmaz.
    assert sum(1 for c in candles if c.high == c.low) == 55
    assert all(c.low <= c.close <= c.high for c in candles)


# --- takvim ve toplama -------------------------------------------------------------

def test_haftalik_toplama_sentetik_haftada_tam_sayilar():
    rows = [satir("2026-08-24", 100, 110, 90), satir("2026-08-25", 115, 120, 95),
            satir("2026-08-26", 90, 118, 85), satir("2026-08-27", 120, 125, 100),
            satir("2026-08-28", 110, 122, 105)]
    candles, _ = normalize_daily(rows)
    (week,) = aggregate(candles, Timeframe.WEEKLY)
    assert week == Candle(date=date(2026, 8, 24), high=125, low=85, close=110, open=None,
                          volume=None, end_date=date(2026, 8, 28), bars=5)


def test_iki_haftaya_yayilan_seri_iki_mum_verir_ve_sirasiz_girdi_kabul_edilir():
    rows = hafta(date(2026, 8, 24)) + hafta(date(2026, 8, 31), cuma_var=False)
    random.Random(7).shuffle(rows)
    candles, _ = normalize_daily(rows)
    weeks = aggregate(candles, Timeframe.WEEKLY)
    assert [(w.date, w.end_date, w.bars) for w in weeks] == [
        (date(2026, 8, 24), date(2026, 8, 28), 5), (date(2026, 8, 31), date(2026, 9, 3), 4)]
    assert weeks[1].close == 103 and weeks[1].high == 113 and weeks[1].low == 90


def test_donem_anahtarlari_ve_sonlari():
    gun = date(2026, 9, 6)  # pazar
    assert period_key(gun, Timeframe.WEEKLY) == date(2026, 8, 31)
    assert period_end(date(2026, 8, 31), Timeframe.WEEKLY) == date(2026, 9, 6)
    assert period_key(date(2026, 8, 31), Timeframe.WEEKLY) == date(2026, 8, 31)
    assert period_key(gun, Timeframe.MONTHLY) == date(2026, 9, 1)
    assert period_end(date(2026, 2, 1), Timeframe.MONTHLY) == date(2026, 2, 28)
    assert period_end(date(2028, 2, 1), Timeframe.MONTHLY) == date(2028, 2, 29)
    assert period_key(date(2026, 5, 15), Timeframe.QUARTERLY) == date(2026, 4, 1)
    assert period_key(date(2026, 12, 31), Timeframe.QUARTERLY) == date(2026, 10, 1)
    assert period_end(date(2026, 10, 1), Timeframe.QUARTERLY) == date(2026, 12, 31)
    assert period_key(date(2026, 6, 30), Timeframe.SEMIANNUAL) == date(2026, 1, 1)
    assert period_key(date(2026, 7, 1), Timeframe.SEMIANNUAL) == date(2026, 7, 1)
    assert period_end(date(2026, 1, 1), Timeframe.SEMIANNUAL) == date(2026, 6, 30)
    assert period_key(gun, Timeframe.DAILY) == period_end(gun, Timeframe.DAILY) == gun
    # Dönem başı olmayan bir tarih de doğru sona oturur.
    assert period_end(date(2026, 9, 17), Timeframe.QUARTERLY) == date(2026, 9, 30)


def test_toplamada_acilis_ve_hacim_kurali():
    haftalik = [Candle(date(2026, 8, 24), 110, 90, 100, open=None, volume=10),
                Candle(date(2026, 8, 25), 120, 95, 115, open=101, volume=20),
                Candle(date(2026, 8, 26), 118, 85, 90, open=116, volume=5)]
    (week,) = aggregate(haftalik, Timeframe.WEEKLY)
    assert week.open == 101 and week.volume == 35  # ilk boş olmayan açılış, tam toplam
    eksik = haftalik + [Candle(date(2026, 8, 27), 125, 100, 120, open=91, volume=None)]
    (week,) = aggregate(eksik, Timeframe.WEEKLY)
    assert week.volume is None and week.close == 120 and week.bars == 4
    (hepsi_bos,) = aggregate([Candle(date(2026, 8, 24), 110, 90, 100)], Timeframe.WEEKLY)
    assert hepsi_bos.open is None and hepsi_bos.volume is None


def test_gunluk_toplama_kopya_dondurur_ve_aylik_toplama_takvimi_izler():
    rows = hafta(date(2026, 8, 24)) + hafta(date(2026, 8, 31))
    candles, _ = normalize_daily(rows)
    kopya = aggregate(candles, Timeframe.DAILY)
    assert kopya == candles and kopya is not candles
    months = aggregate(candles, Timeframe.MONTHLY)
    assert [(m.date, m.end_date, m.bars) for m in months] == [
        (date(2026, 8, 1), date(2026, 8, 31), 6), (date(2026, 9, 1), date(2026, 9, 4), 4)]
    assert aggregate([], Timeframe.WEEKLY) == []


# --- tamamlanma --------------------------------------------------------------------

def test_cuma_gunu_olusan_hafta_donmez_onceki_hafta_doner():
    candles, _ = normalize_daily(hafta(date(2026, 8, 24)) + hafta(date(2026, 8, 31)))
    period, status = previous_completed_period(candles, Timeframe.WEEKLY, date(2026, 9, 4))
    assert status == "OK" and period is not None
    assert period.date == date(2026, 8, 24) and period.end_date == date(2026, 8, 28)


def test_cumartesi_cuma_mumu_varsa_o_hafta_doner_fixture(gunluk_satirlar):
    candles, _ = normalize_daily(gunluk_satirlar)
    period, status = previous_completed_period(candles, Timeframe.WEEKLY, date(2026, 9, 6))
    assert status == "OK" and period is not None
    assert period.date == date(2026, 8, 31) and period.end_date == date(2026, 9, 4)
    assert (period.high, period.low, period.close, period.bars) == (4537.8, 4292.2, 4476.6, 5)
    # Cumartesi de aynı sonucu verir; kural "cumartesiden itibaren".
    cumartesi, status = previous_completed_period(candles, Timeframe.WEEKLY, date(2026, 9, 5))
    assert status == "OK" and cumartesi == period


def test_cumartesi_cuma_mumu_yoksa_missing_closing_bar():
    candles, _ = normalize_daily(hafta(date(2026, 8, 24)) + hafta(date(2026, 8, 31), cuma_var=False))
    period, status = previous_completed_period(candles, Timeframe.WEEKLY, date(2026, 9, 5))
    assert (period, status) == (None, "MISSING_CLOSING_BAR")
    # Pazartesi de hâlâ hoşgörü içinde.
    assert previous_completed_period(candles, Timeframe.WEEKLY, date(2026, 9, 7))[1] == "MISSING_CLOSING_BAR"


def test_sonraki_sali_cuma_mumu_yoksa_hosgoruyle_ok():
    candles, _ = normalize_daily(hafta(date(2026, 8, 24)) + hafta(date(2026, 8, 31), cuma_var=False))
    period, status = previous_completed_period(candles, Timeframe.WEEKLY, date(2026, 9, 8))
    assert status == "OK" and period is not None
    assert period.date == date(2026, 8, 31) and period.end_date == date(2026, 9, 3) and period.bars == 4
    # Hoşgörü parametreyle uzarsa salı yetmez.
    sıkı = CompletionParams(grace_days=5)
    assert previous_completed_period(candles, Timeframe.WEEKLY, date(2026, 9, 8), sıkı)[1] == "MISSING_CLOSING_BAR"


def test_yalniz_olusan_hafta_varsa_incomplete_period_bos_seride_insufficient():
    candles, _ = normalize_daily(hafta(date(2026, 8, 31)))
    assert previous_completed_period(candles, Timeframe.WEEKLY, date(2026, 9, 4)) == (None, "INCOMPLETE_PERIOD")
    assert previous_completed_period([], Timeframe.WEEKLY, date(2026, 9, 4)) == (None, "INSUFFICIENT_DATA")
    # Gelecek tarihli mumlar da "oluşuyor" sayılır.
    assert previous_completed_period(candles, Timeframe.WEEKLY, date(2026, 8, 20)) == (None, "INCOMPLETE_PERIOD")


def test_veride_hic_olmayan_bitmis_hafta_hosgoru_dolmadan_eski_haftaya_dusmez():
    # Akış bir hafta boyunca kesik: 24–28 Ağustos var, 31 Ağustos haftası hiç yok.
    candles, _ = normalize_daily(hafta(date(2026, 8, 24)))
    assert previous_completed_period(candles, Timeframe.WEEKLY, date(2026, 9, 5)) == (None, "MISSING_CLOSING_BAR")
    period, status = previous_completed_period(candles, Timeframe.WEEKLY, date(2026, 9, 8))
    assert status == "OK" and period is not None and period.date == date(2026, 8, 24)


def test_ay_tamamlanmasi():
    agustos = hafta(date(2026, 8, 24)) + hafta(date(2026, 8, 31))  # 31 Ağustos pazartesi
    candles, _ = normalize_daily(agustos)
    # Ayın son günü henüz ay oluşuyor; öncesinde tamamlanmış ay veride yok.
    assert previous_completed_period(candles, Timeframe.MONTHLY, date(2026, 8, 31)) == (None, "INCOMPLETE_PERIOD")
    period, status = previous_completed_period(candles, Timeframe.MONTHLY, date(2026, 9, 1))
    assert status == "OK" and period is not None
    assert period.date == date(2026, 8, 1) and period.end_date == date(2026, 8, 31) and period.bars == 6
    # Ayın son hafta içi günü (31 Ağustos) eksikse hoşgörü dolana kadar verilmez.
    eksik, _ = normalize_daily(hafta(date(2026, 8, 24)) + hafta(date(2026, 8, 31))[1:])
    assert previous_completed_period(eksik, Timeframe.MONTHLY, date(2026, 9, 1)) == (None, "MISSING_CLOSING_BAR")
    period, status = previous_completed_period(eksik, Timeframe.MONTHLY, date(2026, 9, 2))
    assert status == "OK" and period is not None and period.end_date == date(2026, 8, 28)


def test_ceyrek_ve_yarim_yil_tamamlanmasi(gunluk_satirlar):
    candles, _ = normalize_daily(gunluk_satirlar)
    quarter, status = previous_completed_period(candles, Timeframe.QUARTERLY, date(2026, 9, 6))
    assert status == "OK" and quarter is not None
    assert quarter.date == date(2026, 4, 1) and quarter.end_date == date(2026, 6, 30)
    half, status = previous_completed_period(candles, Timeframe.SEMIANNUAL, date(2026, 9, 6))
    assert status == "OK" and half is not None
    assert half.date == date(2026, 1, 1) and half.end_date == date(2026, 6, 30)
    assert half.high >= quarter.high and half.low <= quarter.low
    gun, status = previous_completed_period(candles, Timeframe.DAILY, date(2026, 9, 6))
    assert status == "OK" and gun is not None and gun.date == date(2026, 9, 4)


# --- normalize_intraday --------------------------------------------------------------

def test_gunici_normalizasyon_acilis_doldurma_ve_hacim_none_kalir():
    rows = [
        {"t": "2026-09-01T04:10:00+00:00", "o": None, "h": 11, "l": 9, "c": 10.5, "v": None},
        {"t": "2026-09-01T04:00:00+00:00", "o": None, "h": 11, "l": 9, "c": 10, "v": 0},
        {"t": "2026-09-01T07:05:00+03:00", "o": 10.2, "h": 11, "l": 9, "c": 10.4, "v": "12"},  # 04:05 UTC
        {"t": "2026-09-01T04:15:00", "o": 10.6, "h": 11, "l": 9, "c": 10.8, "v": -3},          # saat dilimsiz
        {"t": "2026-09-01T04:15:00+00:00", "o": 10.7, "h": 11, "l": 9, "c": 10.9, "v": 4},     # yinelenen, son kalır
        {"t": "2026-09-01T04:20:00+00:00", "o": 1, "h": 11, "l": 9, "c": None, "v": 4},        # bozuk
        {"t": "2026-09-01T04:25:00+00:00", "o": 12, "h": 11, "l": 9, "c": 10, "v": 4},         # açılış aralık dışı
    ]
    bars, quality = normalize_intraday(rows)
    assert [b.time.isoformat() for b in bars] == [
        "2026-09-01T04:00:00+00:00", "2026-09-01T04:05:00+00:00", "2026-09-01T04:10:00+00:00",
        "2026-09-01T04:15:00+00:00", "2026-09-01T04:25:00+00:00"]
    assert all(b.time.tzinfo == timezone.utc for b in bars)
    assert bars[0].open == 10        # ilk mumda açılış yok → kendi kapanışı
    assert bars[2].open == 10.4      # açılış yok → önceki mumun kapanışı
    assert [b.volume for b in bars] == [0, 12, None, 4, 4]
    assert bars[3].close == 10.9     # yinelenen damgada son kayıt
    assert bars[4].high == 12        # aralık açılışı kapsayacak şekilde genişledi
    assert quality.dropped_invalid == 1 and quality.dropped_duplicate == 1 and quality.range_widened == 1
    assert quality.kept == 5 and quality.received == 7 and quality.status == "OK"
    assert quality.first_date == quality.last_date == date(2026, 9, 1)


def test_gunici_fixture_1034_mum(gunici_satirlar):
    bars, quality = normalize_intraday(gunici_satirlar)
    assert len(bars) == 1034 == quality.kept and quality.status == "OK"
    assert all(a.time < b.time for a, b in zip(bars, bars[1:]))
    assert bars[0].time == datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc)
    assert bars[-1].close == 4476.6 and bars[-1].volume == 0
    assert quality.dropped_invalid == quality.dropped_duplicate == quality.range_widened == 0
    assert all(b.low <= b.open <= b.high and b.low <= b.close <= b.high for b in bars)


def test_ayni_girdi_ayni_cikti(gunluk_satirlar, gunici_satirlar):
    karisik = list(gunluk_satirlar)
    random.Random(42).shuffle(karisik)
    a = normalize_daily(karisik)
    b = normalize_daily(list(karisik))
    assert a == b and a[0] == normalize_daily(gunluk_satirlar)[0]
    assert aggregate(a[0], Timeframe.WEEKLY) == aggregate(b[0], Timeframe.WEEKLY)
    bugun = date(2026, 9, 6)
    assert (previous_completed_period(a[0], Timeframe.WEEKLY, bugun)
            == previous_completed_period(b[0], Timeframe.WEEKLY, bugun))
    assert normalize_intraday(gunici_satirlar) == normalize_intraday(list(gunici_satirlar))


def test_daily_aggregate_sirasiz_girdiyi_siralar():
    """DAILY dalı kopya döner ama sıralı: pivot seçimi sırasız listede yanlış 'dün' buluyordu."""
    from datetime import date
    from app.services.technical.candles import Candle, Timeframe, aggregate
    a = Candle(date(2026, 1, 5), 10, 9, 9.5); b = Candle(date(2026, 1, 6), 11, 10, 10.5); c = Candle(date(2026, 1, 7), 12, 11, 11.5)
    out = aggregate([c, a, b], Timeframe.DAILY)
    assert [x.date for x in out] == [a.date, b.date, c.date]
