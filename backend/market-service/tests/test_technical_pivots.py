"""Pivot seviyeleri ve fiyat merdiveni — `technical/pivots.py`.

`frontend/src/domain/pivots.test.ts`'in 14 testi yeni API'ye taşındı; üstüne
Camarilla, dönem düşüşü (kırpık hafta), marjlı merdiven ve **temel eşitliği**
eklendi: canlı (2026-09-06, iki fiyat çerçevesi × 4 varyant) ve altı tarihsel
gün (× 4 varyant) için eski arayüzün ürettiği merdivenler fixture'da duruyor;
buradaki hesap onlarla seviye seviye eşleşmeli (1e-6), en yakın hedefler ve
yerleşim indeksi aynı olmalı.

Arayüz testinden bilinçli ayrılan tek yer: FE'nin sentetik serisi 21 Ağustos'ta
bitiyor ve FE 1 Eylül'de Ağustos'u tamamlanmış sayıyordu. Sunucu kuralı 31
Ağustos kapanış mumunu ister; mum yokken ve hoşgörü dolmamışken Temmuz'a düşer
(`PERIOD_INCOMPLETE_FALLBACK`), 2 Eylül'de Ağustos'u verir.
"""
import json
import random
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.services.technical.candles import Candle, normalize_daily
from app.services.technical.pivots import (
    PivotMethod, PivotParams, PivotPeriod, PivotSet, build_ladder, compute_all, pivot_levels,
)

FIXTURES = Path(__file__).parent / "fixtures"
CLASSIC, FIB, CAM = PivotMethod.CLASSIC, PivotMethod.FIBONACCI, PivotMethod.CAMARILLA
DAILY, WEEKLY, MONTHLY = PivotPeriod.DAILY, PivotPeriod.WEEKLY, PivotPeriod.MONTHLY
LIVE_TODAY = date(2026, 9, 6)

# Temel fixture'larındaki varyant anahtarları → (dönem, yöntem).
VARIANTS = {"weekly_fib": (WEEKLY, FIB), "weekly_classic": (WEEKLY, CLASSIC),
            "monthly_fib": (MONTHLY, FIB), "monthly_classic": (MONTHLY, CLASSIC)}


def mum(d: str, h: float, l: float, c: float) -> Candle:
    return Candle(date=date.fromisoformat(d), high=h, low=l, close=c)


def hafta(pazartesi: str, base: float, gun: int = 5) -> list[Candle]:
    """FE testindeki `week()`: pazartesi'den `gun` mum; h = base+10+i, l = base−10+i, c = base+i."""
    start = date.fromisoformat(pazartesi)
    return [Candle(date=start + timedelta(days=i), high=base + 10 + i, low=base - 10 + i, close=base + i)
            for i in range(gun)]


def seviyeler(pivot_set: PivotSet) -> dict[str, float]:
    return dict(pivot_set.levels)


@pytest.fixture(scope="module")
def fixture_mumlari() -> list[Candle]:
    points = json.loads((FIXTURES / "xau_daily_20260906.json").read_text())["points"]
    candles, quality = normalize_daily(points)
    assert quality.status == "OK" and len(candles) == 1257
    return candles


@pytest.fixture(scope="module")
def canli_temel() -> dict:
    return json.loads((FIXTURES / "baseline_live_20260906.json").read_text())


@pytest.fixture(scope="module")
def tarihsel_temel() -> list[dict]:
    return json.loads((FIXTURES / "baseline_history_20260906.json").read_text())


# --- FE portu: computePivots ----------------------------------------------------------

TODAY = date(2026, 3, 6)  # ölçümün sabit kalması için "bugün" her çağrıda açıkça verilir

# İki tam ay + içinde bulunulan ay: son tamamlanan ay Şubat olmalı.
SERIES = (
    [mum(f"2026-01-{i + 1:02d}", 110, 90, 100) for i in range(20)]
    + [mum(f"2026-02-{i + 1:02d}", 130, 70, 120) for i in range(20)]
    + [mum(f"2026-03-{i + 1:02d}", 200, 60, 150) for i in range(5)]
)


def test_yetersiz_mumda_insufficient_data_ve_bos_seviye():
    sets = compute_all(SERIES[:39], TODAY)
    for period in PivotPeriod:
        for method in PivotMethod:
            s = sets[period][method]
            assert (s.status, s.levels, s.period_id, s.completion) == ("INSUFFICIENT_DATA", (), "", "NONE")
            assert s.high is None and s.start is None and s.bars == 0 and s.missing_bar_for is None
    # Sınır tam 40'ta: kırkıncı mumla hesap yapılır.
    assert compute_all(SERIES[:40], TODAY)[MONTHLY][CLASSIC].status == "OK"


def test_icinde_bulunulan_donem_atlanip_son_tamamlanan_ay_kullanilir():
    sets = compute_all(SERIES, TODAY)
    for method in PivotMethod:
        s = sets[MONTHLY][method]
        assert s.period_id == "2026-02" and s.status == "OK"  # Mart devam ediyor, sayılmaz
        assert (s.high, s.low, s.close, s.bars) == (130, 70, 120, 20)
        assert (s.start, s.end) == (date(2026, 2, 1), date(2026, 2, 20))
    # Şubat'ın son hafta içi günü (27'si) veride yok ama Mart mumları var: dönem geride kaldı.
    assert sets[MONTHLY][CLASSIC].completion == "SUCCEEDED_BY_LATER_BAR"


def test_klasik_pivot_formulu():
    lv = seviyeler(compute_all(SERIES, TODAY)[MONTHLY][CLASSIC])
    h, l, c = 130, 70, 120
    p = (h + l + c) / 3
    assert lv["P"] == pytest.approx(p, abs=1e-10)
    assert lv["R1"] == pytest.approx(2 * p - l, abs=1e-10)
    assert lv["S1"] == pytest.approx(2 * p - h, abs=1e-10)
    assert lv["R2"] == pytest.approx(p + (h - l), abs=1e-10)
    assert lv["S2"] == pytest.approx(p - (h - l), abs=1e-10)
    assert lv["R3"] == pytest.approx(h + 2 * (p - l), abs=1e-10)
    assert lv["S3"] == pytest.approx(l - 2 * (h - p), abs=1e-10)


def test_fibonacci_seviyeleri_araligin_382_618_100_kati():
    lv = seviyeler(compute_all(SERIES, TODAY)[MONTHLY][FIB])
    r = 130 - 70
    assert lv["R1"] - lv["P"] == pytest.approx(0.382 * r, abs=1e-10)
    assert lv["P"] - lv["S2"] == pytest.approx(0.618 * r, abs=1e-10)
    assert lv["R3"] - lv["P"] == pytest.approx(r, abs=1e-10)


# --- FE portu: buildLadder ------------------------------------------------------------

SET = (("R3", 130.0), ("R2", 120.0), ("R1", 110.0), ("P", 100.0), ("S1", 90.0), ("S2", 80.0), ("S3", 70.0))


def test_merdiven_seviyeleri_buyukten_kucuge_siralar():
    ladder = build_ladder(SET[::-1], 100)  # sırasız verilse de
    assert [i.name for i in ladder.items] == ["R3", "R2", "R1", "P", "S1", "S2", "S3"]


def test_fiyat_araligin_ortasindayken_dogru_yere_yerlesir():
    ladder = build_ladder(SET, 105)
    assert ladder.items[ladder.insert_at].name == "P"  # işaretçi P'nin ÖNÜNE gelir
    assert ladder.nearest_up == "R1" and ladder.nearest_down == "P"
    assert ladder.outside is None and ladder.testing == () and ladder.position_vs_pivot == "ABOVE"
    assert {i.name: i.role for i in ladder.items} == {
        "R3": None, "R2": None, "R1": "NEAREST_UP", "P": "NEAREST_DOWN", "S1": None, "S2": None, "S3": None}


def test_fiyat_tum_seviyelerin_ustundeyse_en_basa_yerlesir():
    # Aylık pivot geride kaldığında fiyat hepsinin üstünde kalıyor ve "şu an"
    # satırı hiç görünmüyordu; bu test o regresyonu kilitler.
    ladder = build_ladder(SET, 500)
    assert ladder.insert_at == 0 and ladder.nearest_up is None and ladder.nearest_down == "R3"
    assert ladder.outside == "ABOVE_ALL" and ladder.position_vs_pivot == "ABOVE"
    assert not any(i.above for i in ladder.items)


def test_fiyat_tum_seviyelerin_altindaysa_en_sona_yerlesir():
    ladder = build_ladder(SET, 10)
    assert ladder.insert_at == len(ladder.items) == 7
    assert ladder.nearest_up == "S3" and ladder.nearest_down is None
    assert ladder.outside == "BELOW_ALL" and ladder.position_vs_pivot == "BELOW"
    assert all(i.above for i in ladder.items)


def test_uzaklik_yuzdesi_fiyata_gore_hesaplanir():
    ladder = build_ladder(SET, 100)
    r2 = next(i for i in ladder.items if i.name == "R2")
    assert r2.distance == pytest.approx(0.2, abs=1e-10)
    assert r2.distance_usd == pytest.approx(20) and r2.distance_atr is None
    assert build_ladder(SET, 100, atr=5).items[1].distance_atr == pytest.approx(4)
    assert build_ladder(SET, 100, atr=0).items[1].distance_atr is None  # sıfır ATR ölçü değil


# --- FE portu: tamamlanmış dönem seçimi --------------------------------------------------

# 40 mum alt sınırını aşmak için 10 hafta; son dördü ölçülen değerlerle aynı.
HAFTALAR = (
    [c for i, monday in enumerate(["2026-06-08", "2026-06-15", "2026-06-22", "2026-06-29",
                                   "2026-07-06", "2026-07-13", "2026-07-20"])
     for c in hafta(monday, 3900 + i * 20)]
    + hafta("2026-07-27", 4050) + hafta("2026-08-03", 4340)
    + hafta("2026-08-10", 4380) + hafta("2026-08-17", 4620)
)


def test_hafta_cuma_kapanisiyla_tamamlanmis_sayilir():
    # Kod her zaman sondan bir önceki grubu alıyordu: cuma kapanmış olsa bile içinde
    # bulunulan hafta "devam ediyor" sayılıyor, seviyeler bir hafta bayat kalıyordu.
    for today in (date(2026, 8, 22), date(2026, 8, 24)):
        s = compute_all(HAFTALAR, today)[WEEKLY][CLASSIC]
        assert (s.period_id, s.status, s.completion) == ("2026-08-17", "OK", "LAST_BAR_PRESENT")


def test_hafta_surerken_onceki_hafta_kullanilir():
    for today in (date(2026, 8, 19), date(2026, 8, 17)):
        assert compute_all(HAFTALAR, today)[WEEKLY][FIB].period_id == "2026-08-10"


def test_ay_ancak_bittiginde_tamamlanmis_sayilir():
    assert compute_all(HAFTALAR, date(2026, 8, 22))[MONTHLY][CLASSIC].period_id == "2026-07"
    # FE 1 Eylül'de Ağustos'u veriyordu; seri 21 Ağustos'ta bittiği için 31 Ağustos
    # kapanış mumu yok. Sunucu kırpık aydan pivot üretmez: hoşgörü dolana kadar
    # Temmuz'a düşer ve eksik mumu bildirir; 2 Eylül'de Ağustos'u verir.
    eylul_1 = compute_all(HAFTALAR, date(2026, 9, 1))[MONTHLY][CLASSIC]
    assert (eylul_1.period_id, eylul_1.status, eylul_1.missing_bar_for) == (
        "2026-07", "PERIOD_INCOMPLETE_FALLBACK", date(2026, 8, 31))
    eylul_2 = compute_all(HAFTALAR, date(2026, 9, 2))[MONTHLY][CLASSIC]
    assert (eylul_2.period_id, eylul_2.status, eylul_2.completion, eylul_2.missing_bar_for) == (
        "2026-08", "OK", "GRACE_ELAPSED", None)


def test_hicbir_donem_tamamlanmadiysa_period_unavailable():
    # Bugün ilk haftanın içinde. `today`'e kadar yalnız 3 mum görünür → varsayılan
    # eşikte INSUFFICIENT_DATA; eşik gevşetilince asıl neden: tamamlanmış hafta yok.
    assert compute_all(HAFTALAR, date(2026, 6, 10))[WEEKLY][CLASSIC].status == "INSUFFICIENT_DATA"
    sets = compute_all(HAFTALAR, date(2026, 6, 10), PivotParams(min_candles=1))
    s = sets[WEEKLY][CLASSIC]
    assert (s.status, s.levels, s.missing_bar_for, s.period_id) == ("PERIOD_UNAVAILABLE", (), None, "")
    assert sets[MONTHLY][CLASSIC].status == "PERIOD_UNAVAILABLE"
    assert sets[DAILY][CLASSIC].period_id == "2026-06-09"  # dün bitti, günlük pivot var


def test_secilen_donemin_yuksek_dusuk_kapanisi_dogru_toplanir():
    s = compute_all(HAFTALAR, date(2026, 8, 22))[WEEKLY][CLASSIC]
    h, l, c = 4634, 4610, 4624  # 17–21 haftası: h = 4620+10+4, l = 4620−10, c = 4620+4
    assert (s.high, s.low, s.close, s.bars, s.start, s.end) == (h, l, c, 5, date(2026, 8, 17), date(2026, 8, 21))
    lv = seviyeler(s)
    assert lv["P"] == pytest.approx((h + l + c) / 3, abs=1e-9)
    assert lv["R1"] == pytest.approx(2 * ((h + l + c) / 3) - l, abs=1e-9)


# --- yöntemler ---------------------------------------------------------------------------

def test_camarilla_dokuz_seviye_simetrik_ve_degere_gore_sirali():
    lv = pivot_levels(110, 90, 100, CAM)
    assert [n for n, _ in lv] == ["R4", "R3", "R2", "R1", "P", "S1", "S2", "S3", "S4"]
    d = dict(lv)
    assert d["P"] == pytest.approx(100)
    for k, m in zip(range(1, 5), (1 / 12, 1 / 6, 1 / 4, 1 / 2)):
        assert d[f"R{k}"] - 100 == pytest.approx(20 * 1.1 * m, abs=1e-9)
        assert d[f"R{k}"] - 100 == pytest.approx(100 - d[f"S{k}"], abs=1e-9)  # R_k − C == C − S_k
    values = [v for _, v in lv]
    assert values == sorted(values, reverse=True)


def test_camarilla_kapanis_ucta_iken_s_seviyeleri_p_ustune_cikar():
    lv = pivot_levels(110, 90, 110, CAM)  # kapanış = yüksek
    assert [n for n, _ in lv] == ["R4", "R3", "R2", "R1", "S1", "S2", "S3", "P", "S4"]
    values = [v for _, v in lv]
    assert values == sorted(values, reverse=True)
    d = dict(lv)
    assert d["S3"] > d["P"] > d["S4"] and d["P"] == pytest.approx((110 + 90 + 110) / 3)


def test_fibonacci_r3_klasik_r2_ile_s3_klasik_s2_ile_ayni():
    h, l, c = 4537.8, 4292.2, 4476.6
    classic, fib = dict(pivot_levels(h, l, c, CLASSIC)), dict(pivot_levels(h, l, c, FIB))
    assert fib["R3"] == classic["R2"] and fib["S3"] == classic["S2"] and fib["P"] == classic["P"]
    assert [n for n, _ in pivot_levels(h, l, c, FIB)] == ["R3", "R2", "R1", "P", "S1", "S2", "S3"]


def test_aralik_sifirken_tum_seviyeler_esit_ve_sira_kararli():
    # Fixture'da 55 gün h == l; seviyeler çakışır ama adlandırma sırası bozulmaz.
    beklenen = {CLASSIC: ["R3", "R2", "R1", "P", "S1", "S2", "S3"],
                FIB: ["R3", "R2", "R1", "P", "S1", "S2", "S3"],
                CAM: ["R4", "R3", "R2", "R1", "P", "S1", "S2", "S3", "S4"]}
    for method, names in beklenen.items():
        lv = pivot_levels(100, 100, 100, method)
        assert [n for n, _ in lv] == names and all(v == 100 for _, v in lv)


def test_gecersiz_mum_valueerror():
    with pytest.raises(ValueError):
        pivot_levels(90, 110, 100, CLASSIC)  # high < low
    with pytest.raises(ValueError):
        pivot_levels(float("nan"), 90, 100, FIB)
    with pytest.raises(ValueError):
        pivot_levels(110, 90, float("inf"), CAM)


def test_ozel_parametreler_ad_ve_degeri_belirler():
    params = PivotParams(fib_ratios=(0.5,), camarilla_k=1.0, camarilla_multipliers=(0.25, 0.5))
    fib = pivot_levels(110, 90, 100, FIB, params)
    assert [n for n, _ in fib] == ["R1", "P", "S1"] and dict(fib)["R1"] == pytest.approx(110)
    cam = pivot_levels(110, 90, 100, CAM, params)
    assert [n for n, _ in cam] == ["R2", "R1", "P", "S1", "S2"] and dict(cam)["R2"] == pytest.approx(110)
    assert pivot_levels(110, 90, 100, "CLASSIC") == pivot_levels(110, 90, 100, CLASSIC)  # type: ignore[arg-type]


# --- dönem düşüşü ve görünürlük ---------------------------------------------------------

def test_cumartesi_cuma_mumu_yoksa_onceki_haftaya_duser():
    # 9 tam hafta + kırpık hafta (pazartesi–perşembe): ölçülen hata (503 + 300 sn önbellek).
    mondays = [date(2026, 6, 29) + timedelta(days=7 * i) for i in range(9)]
    candles = ([c for i, m in enumerate(mondays) for c in hafta(m.isoformat(), 4000 + 10 * i)]
               + hafta("2026-08-31", 4200, gun=4))
    sets = compute_all(candles, date(2026, 9, 5))
    for method in PivotMethod:
        s = sets[WEEKLY][method]
        assert (s.status, s.period_id, s.missing_bar_for) == (
            "PERIOD_INCOMPLETE_FALLBACK", "2026-08-24", date(2026, 9, 4))
        assert (s.completion, s.end, s.bars) == ("LAST_BAR_PRESENT", date(2026, 8, 28), 5)
        assert len(s.levels) == (9 if method is CAM else 7)
    # Seviyeler kırpık haftadan değil, önceki tam haftadan.
    onceki = hafta("2026-08-24", 4080)
    h, l, c = max(x.high for x in onceki), min(x.low for x in onceki), onceki[-1].close
    assert sets[WEEKLY][CLASSIC].levels == pivot_levels(h, l, c, CLASSIC)
    # Günlük dönem de aynı kuralda: cuma mumu beklenirken perşembeye düşer.
    d = sets[DAILY][CLASSIC]
    assert (d.status, d.period_id, d.missing_bar_for) == (
        "PERIOD_INCOMPLETE_FALLBACK", "2026-09-03", date(2026, 9, 4))
    # Aylık etkilenmez: 31 Ağustos mumu var.
    assert (sets[MONTHLY][CLASSIC].status, sets[MONTHLY][CLASSIC].period_id) == ("OK", "2026-08")
    # Salı hoşgörü dolar: kırpık hafta 4 mumla kabul edilir ve bunu söyler.
    sali = compute_all(candles, date(2026, 9, 8))[WEEKLY][CLASSIC]
    assert (sali.period_id, sali.status, sali.completion, sali.bars, sali.missing_bar_for) == (
        "2026-08-31", "OK", "GRACE_ELAPSED", 4, None)


def test_dususte_eski_donem_yoksa_period_unavailable():
    candles = hafta("2026-08-31", 4200, gun=4)
    s = compute_all(candles, date(2026, 9, 5), PivotParams(min_candles=1))[WEEKLY][FIB]
    assert (s.status, s.levels, s.missing_bar_for, s.period_id) == (
        "PERIOD_UNAVAILABLE", (), date(2026, 9, 4), "")


def test_gunluk_donem_olusan_gunu_atlar(fixture_mumlari):
    # 4 Eylül cuma: o günün mumu veride var ama gün "oluşuyor" → 3 Eylül.
    assert compute_all(fixture_mumlari, date(2026, 9, 4))[DAILY][CLASSIC].period_id == "2026-09-03"
    s = compute_all(fixture_mumlari, LIVE_TODAY)[DAILY][CLASSIC]
    assert s.period_id == "2026-09-04" and s.start == s.end == date(2026, 9, 4) and s.bars == 1
    assert (s.high, s.low, s.close) == (4537.8, 4412.0, 4476.6)


def test_period_id_bicimleri_ve_donem_sinirlari(fixture_mumlari):
    sets = compute_all(fixture_mumlari, LIVE_TODAY)
    d, w, m = sets[DAILY][CAM], sets[WEEKLY][CAM], sets[MONTHLY][CAM]
    assert (d.period_id, w.period_id, m.period_id) == ("2026-09-04", "2026-08-31", "2026-08")
    assert (w.start, w.end, w.bars) == (date(2026, 8, 31), date(2026, 9, 4), 5)
    assert (m.start, m.end, m.bars) == (date(2026, 8, 1), date(2026, 8, 31), 21)
    assert all(s.status == "OK" and s.completion == "LAST_BAR_PRESENT" and s.missing_bar_for is None
               for by_method in sets.values() for s in by_method.values())
    assert {(s.period, s.method) for by_method in sets.values() for s in by_method.values()} == {
        (p, mth) for p in PivotPeriod for mth in PivotMethod}


def test_gelecek_tarihli_mumlar_gorulmez(fixture_mumlari):
    # Aynı seri üzerinde 24 Mart 2026'ya bakmak, o gün görünen veriyi görür.
    today = date(2026, 3, 24)
    kirpik = [c for c in fixture_mumlari if c.date <= today]
    assert compute_all(fixture_mumlari, today) == compute_all(kirpik, today)


def test_ayni_girdi_ayni_cikti_sirasiz_girdi(fixture_mumlari):
    karisik = list(fixture_mumlari)
    random.Random(3).shuffle(karisik)
    assert compute_all(karisik, LIVE_TODAY) == compute_all(fixture_mumlari, LIVE_TODAY)


# --- merdiven: marj ---------------------------------------------------------------------

def _fe_build_ladder(levels, price: float) -> dict:
    """`buildLadder` (pivots.ts) birebir: above = value >= price, nearestUp =
    üsttekilerin sonuncusu, nearestDown = alttakilerin ilki, insertAt = ilk alttaki."""
    items = sorted(({"name": n, "value": v, "distance": v / price - 1, "above": v >= price}
                    for n, v in levels), key=lambda i: i["value"], reverse=True)
    below = next((k for k, i in enumerate(items) if not i["above"]), -1)
    ups = [i for i in items if i["above"]]
    downs = [i for i in items if not i["above"]]
    return {"items": items, "insertAt": len(items) if below < 0 else below,
            "nearestUp": ups[-1]["name"] if ups else None,
            "nearestDown": downs[0]["name"] if downs else None}


def test_marj_sifir_arayuz_kuraliyla_birebir(fixture_mumlari):
    sets = compute_all(fixture_mumlari, LIVE_TODAY)
    for period in (WEEKLY, MONTHLY):
        for method in (CLASSIC, FIB):
            levels = sets[period][method].levels
            values = [v for _, v in levels]
            prices = ([v + delta for v in values for delta in (-0.5, 0.5)]
                      + [min(values) - 100, max(values) + 100])
            for price in prices:
                fe, be = _fe_build_ladder(levels, price), build_ladder(levels, price)
                assert (be.nearest_up, be.nearest_down, be.insert_at) == (
                    fe["nearestUp"], fe["nearestDown"], fe["insertAt"])
                assert [(i.name, i.value, i.distance, i.above) for i in be.items] == [
                    (i["name"], i["value"], i["distance"], i["above"]) for i in fe["items"]]
                assert be.testing == () and be.margin_usd == 0


def test_fiyat_seviyeye_tam_esitse_seviye_test_ediliyor_sayilir():
    # Arayüz eşit seviyeyi hedef sayardı; burada üzerinde durulan seviye hedef değildir.
    ladder = build_ladder(SET, 100)  # marj 0, fiyat tam P'de
    assert ladder.testing == ("P",) and ladder.position_vs_pivot == "AT"
    assert ladder.nearest_up == "R1" and ladder.nearest_down == "S1"
    assert ladder.insert_at == 4 and next(i for i in ladder.items if i.name == "P").above


def test_marj_test_edilen_seviyeyi_hedeften_cikarir():
    ladder = build_ladder(SET, 101, margin_usd=2)
    assert ladder.testing == ("P",) and ladder.nearest_up == "R1" and ladder.nearest_down == "S1"
    assert ladder.position_vs_pivot == "AT" and ladder.margin_usd == 2
    roles = {i.name: i.role for i in ladder.items}
    assert (roles["P"], roles["R1"], roles["S1"]) == ("TESTING", "NEAREST_UP", "NEAREST_DOWN")
    assert ladder.insert_at == 3  # 101 > 100: P fiyatın altında kaldı
    # Geniş marj birden çok seviyeyi test edilen sayar; adlar merdiven sırasında.
    genis = build_ladder(SET, 100, margin_usd=10)
    assert genis.testing == ("R1", "P", "S1") and genis.nearest_up == "R2" and genis.nearest_down == "S2"
    # Marj tüm seviyeleri kapsarsa hedef yok ama merdivenin dışında da değil.
    hepsi = build_ladder(SET, 100, margin_usd=50)
    assert hepsi.nearest_up is None and hepsi.nearest_down is None and hepsi.outside is None
    assert len(hepsi.testing) == 7


def test_bos_seviye_listesi():
    ladder = build_ladder((), 100)
    assert ladder.items == () and ladder.insert_at == 0
    assert ladder.nearest_up is None and ladder.nearest_down is None
    assert ladder.outside is None and ladder.position_vs_pivot is None and ladder.testing == ()


def test_pivot_yoksa_konum_yok_ve_band_parametreden():
    ladder = build_ladder((("R1", 110.0), ("S1", 90.0)), 100, params=PivotParams(ladder_band_pct=0.01))
    assert ladder.position_vs_pivot is None
    assert ladder.items[0].band == (pytest.approx(108.9), pytest.approx(111.1))
    assert build_ladder(SET, 100).items[0].band == (pytest.approx(130 * 0.9975), pytest.approx(130 * 1.0025))


def test_gecersiz_fiyat_marj_atr_valueerror():
    for price in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            build_ladder(SET, price)
    with pytest.raises(ValueError):
        build_ladder(SET, 100, margin_usd=-1)
    with pytest.raises(ValueError):
        build_ladder(SET, 100, atr=-1)
    with pytest.raises(ValueError):
        build_ladder((("R1", float("nan")),), 100)


# --- temel eşitliği: eski arayüzün ürettiği merdivenler -----------------------------------

def _ladders_at(live: dict, prefix: str) -> dict:
    # Canlı fixture'da anahtar açıklama taşıyor: "ladders_at_harem_spot_4431.6 (what the app shows)".
    return live[next(k for k in live if k.startswith(prefix))]


def test_temel_canli_donem_mumlari_ve_seviyeler(fixture_mumlari, canli_temel):
    assert canli_temel["today_used_by_computePivots"] == LIVE_TODAY.isoformat()
    sets = compute_all(fixture_mumlari, LIVE_TODAY)
    bars = canli_temel["period_bars"]
    w, m = sets[WEEKLY][CLASSIC], sets[MONTHLY][CLASSIC]
    assert (w.period_id, w.high, w.low, w.close) == (bars["weekly"]["id"], 4537.8, 4292.2, 4476.6)
    assert (m.period_id, m.high, m.low, m.close) == (bars["monthly"]["id"], 4670.9, 4026.5, 4431.1)
    # Pivot ve aralık bit-bit aynı: işlem sırası arayüzle birebir.
    assert seviyeler(w)["P"] == bars["weekly"]["pivot"] and w.high - w.low == bars["weekly"]["range"]
    assert seviyeler(m)["P"] == bars["monthly"]["pivot"] and m.high - m.low == bars["monthly"]["range"]
    expected = {
        (WEEKLY, CLASSIC): {"P": 4435.533, "R1": 4578.867, "R2": 4681.133, "R3": 4824.467,
                            "S1": 4333.267, "S2": 4189.933, "S3": 4087.667},
        (WEEKLY, FIB): {"R1": 4529.353, "R2": 4587.314, "R3": 4681.133,
                        "S1": 4341.714, "S2": 4283.753, "S3": 4189.933},
        (MONTHLY, CLASSIC): {"P": 4376.167, "R1": 4725.833, "R2": 5020.567, "R3": 5370.233,
                             "S1": 4081.433, "S2": 3731.767, "S3": 3437.033},
        (MONTHLY, FIB): {"R1": 4622.327, "R2": 4774.406, "R3": 5020.567,
                         "S1": 4130.006, "S2": 3977.927, "S3": 3731.767},
    }
    for (period, method), levels in expected.items():
        got = seviyeler(sets[period][method])
        for name, value in levels.items():
            assert got[name] == pytest.approx(value, abs=1e-3), (period, method, name)


@pytest.mark.parametrize("prefix,price", [("ladders_at_harem_spot_4431.6", 4431.6),
                                          ("ladders_at_last_close_4476.6", 4476.6)])
def test_temel_canli_merdivenler_iki_fiyat_cercevesinde(fixture_mumlari, canli_temel, prefix, price):
    sets = compute_all(fixture_mumlari, LIVE_TODAY)
    ladders = _ladders_at(canli_temel, prefix)
    for key, (period, method) in VARIANTS.items():
        fx = ladders[key]
        assert fx["price"] == price and fx["id"] == sets[period][method].period_id
        ladder = build_ladder(sets[period][method].levels, price)
        assert (ladder.nearest_up, ladder.nearest_down, ladder.insert_at) == (
            fx["nearestUp"], fx["nearestDown"], fx["insertAt"]), key
        assert [i.name for i in ladder.items] == list(fx["levels"])
        for item in ladder.items:
            assert item.value == pytest.approx(fx["levels"][item.name], abs=1e-3), (key, item.name)  # 4 ondalık
            assert item.distance * 100 == pytest.approx(fx["distance_pct"][item.name], abs=1e-3), (key, item.name)


def test_temel_canli_en_yakin_hedefler_spot_ve_kapanista(fixture_mumlari):
    levels = compute_all(fixture_mumlari, LIVE_TODAY)[WEEKLY][FIB].levels
    spot = build_ladder(levels, 4431.6)
    assert (spot.nearest_up, spot.nearest_down, spot.insert_at) == ("P", "S1", 4)
    close = build_ladder(levels, 4476.6)
    assert (close.nearest_up, close.nearest_down, close.insert_at) == ("R1", "P", 3)


def test_temel_canli_dokunma_marji_p_yi_test_edilen_yapar(fixture_mumlari, canli_temel):
    # Arayüzün `touchingLevel`'ı aynı gün P'yi "dokunulan" raporladı (marj %0,2722 ≈ 12 $).
    bp = canli_temel["fe_break_potential"]
    levels = compute_all(fixture_mumlari, LIVE_TODAY)[WEEKLY][FIB].levels
    ladder = build_ladder(levels, bp["app_price"], margin_usd=bp["app_price"] * bp["touch_margin_pct"] / 100)
    assert ladder.testing == (bp["touching"]["name"],) == ("P",)
    assert ladder.position_vs_pivot == "AT" and ladder.nearest_up == "R1" and ladder.nearest_down == "S1"


def test_temel_tarihsel_alti_gun_seviye_ve_hedefler(fixture_mumlari, tarihsel_temel):
    assert len(tarihsel_temel) == 6
    for entry in tarihsel_temel:
        today = date.fromisoformat(entry["today"])
        assert entry["date"] == entry["today"]
        candles = [c for c in fixture_mumlari if c.date <= today]
        assert len(candles) == entry["candles_used"] and candles[-1].close == entry["price"]
        sets = compute_all(candles, today)
        for key, (period, method) in VARIANTS.items():
            fx_pivots = entry["pivots"][period.value.lower()]
            fx_key = "fib" if method is FIB else "classic"
            s = sets[period][method]
            assert s.period_id == fx_pivots["id"] == entry[key]["id"] and s.status == "OK", (entry["date"], key)
            got = seviyeler(s)
            assert got["P"] == pytest.approx(fx_pivots["pivot"], abs=1e-6)
            for name in ("r3", "r2", "r1", "s1", "s2", "s3"):
                assert got[name.upper()] == pytest.approx(fx_pivots[fx_key][name], abs=1e-6), (entry["date"], key, name)
            fx = entry[key]
            ladder = build_ladder(s.levels, entry["price"])
            assert (ladder.nearest_up, ladder.nearest_down, ladder.insert_at) == (
                fx["nearestUp"], fx["nearestDown"], fx["insertAt"]), (entry["date"], key)  # null ↔ None
            assert len(ladder.items) == len(fx["items"]) == 7
            for item, fx_item in zip(ladder.items, fx["items"]):
                assert item.name == fx_item["name"]
                assert item.value == pytest.approx(fx_item["value"], abs=1e-6)
                assert item.distance == pytest.approx(fx_item["distance"], abs=1e-9)
                assert item.above is fx_item["above"]
