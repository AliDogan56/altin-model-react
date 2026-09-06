"""Yapısal destek/direnç motoru (`technical/levels.py`).

Seriler elle kurulur ve yapısı bilinir: testere dişi (100 ↔ 120, adım 2) her
döngüde aynı dip ve tepeyi üretir, dolayısıyla temas sayısı ve sınıfı önceden
bellidir. Temas ve güç formülleri sabit ATR serisiyle **tam değer** olarak,
seçim ve sıralama ise `analyze_levels` üzerinden eşitsizlikle sabitlenir.
"""
import json
import math
import time
from dataclasses import replace
from datetime import date, timedelta
from itertools import combinations
from pathlib import Path

import pytest

from app.services.technical.candles import Candle, normalize_daily
from app.services.technical.indicators import atr
from app.services.technical.levels import (
    CLASS_BREAK, CLASS_NEUTRAL, CLASS_PENDING, CLASS_REJECTION, KIND_RESISTANCE,
    KIND_SUPPORT, LABEL_MODERATE, LABEL_STRONG, LABEL_WEAK, NO_VALID_RESISTANCE,
    NO_VALID_SUPPORT, SIDE_ABOVE, SIDE_BELOW, SIDE_OK, SOURCE_PIVOT, SOURCE_RANGE,
    SOURCE_ROUND, SOURCE_SWING, STATUS_FLAT_MARKET, STATUS_INSUFFICIENT_DATA, STATUS_OK,
    Candidate, LevelParams, Levels, TouchEvent, Zone, analyze_levels, candidates,
    cluster_zones, score_zone, strength_label, touch_events,
)

FIXTURE = Path(__file__).parent / "fixtures" / "xau_daily_20260906.json"
HAFTALIK_KLASIK = [("R3", 4824.467), ("R2", 4681.133), ("R1", 4578.867), ("P", 4435.533),
                   ("S1", 4333.267), ("S2", 4189.933), ("S3", 4087.667)]
BASLANGIC = date(2025, 1, 1)


def mumlar(kapanislar, r=1.0, start=BASLANGIC):
    """Kapanış ± r aralıklı, ardışık takvim günlü mumlar (yaş = indeks farkı)."""
    return [Candle(date=start + timedelta(days=i), high=c + r, low=c - r, close=c)
            for i, c in enumerate(kapanislar)]


def disli(dongu, alt=100.0, ust=120.0, adim=2.0):
    """100→118→120→102 … : dipler 0, 20, 40… tepeler 10, 30, 50… indekslerinde."""
    out = []
    for _ in range(dongu):
        out += [alt + adim * k for k in range(int((ust - alt) / adim))]
        out += [ust - adim * k for k in range(int((ust - alt) / adim))]
    return out


def gurultulu_disli(dongu):
    """Belirlenimci sözde gürültü: eşit fiyat ve sınır üstü değer kalmasın."""
    return [c + ((i * 7919) % 97) / 97.0 * 0.8 - 0.4 for i, c in enumerate(disli(dongu))]


def sabit_atr(n, a=1.0):
    return [a] * n


def olay(klass, weight=1.0, rejection=None, end=0, side=SIDE_ABOVE):
    return TouchEvent(end, end, BASLANGIC + timedelta(days=end), side, klass, rejection, weight)


SWING = Candidate(100.0, SOURCE_SWING, "SWING_LOW", 1.0, BASLANGIC, True, 10)
PIVOT = Candidate(100.2, SOURCE_PIVOT, "S1", 0.8, None, True, None)
RANGE = Candidate(99.9, SOURCE_RANGE, "LOW_60", 0.7, BASLANGIC, True, 12)
ROUND = Candidate(100.0, SOURCE_ROUND, "ROUND", 0.2, None, True, None)
ZONE_LOW, ZONE_HIGH = 99.5, 100.5   # sabit ATR 1 → temas marjı 0,25, uzak kapanış 1,0


def bolge(lv: Levels, orta: float, pay: float = 1.5) -> Zone:
    eslesen = [z for z in lv.zones if abs(z.mid - orta) <= pay]
    assert eslesen, f"{orta} çevresinde bölge yok: {[round(z.mid, 1) for z in lv.zones]}"
    return eslesen[0]


# --- adaylar -------------------------------------------------------------------

def test_adaylar_kaynak_agirlik_ve_tarama_araligi():
    bars = mumlar(disli(3))
    seri = atr(bars, 14)
    cands = candidates(bars, seri, 110.0, [("P", 110.0), ("UZAK", 1000.0)])
    by_type = {}
    for c in cands:
        by_type.setdefault(c.source_type, []).append(c)
    swings = by_type[SOURCE_SWING]
    assert {c.price for c in swings} <= {99.0, 121.0, 101.0}
    assert all(c.weight == 1.0 and c.confirmed for c in swings if c.price != 101.0)
    assert [(c.label, c.weight, c.index) for c in by_type[SOURCE_PIVOT]] == [("P", 0.8, None)]
    # 20 ve 60 günlük uç aynı mumsa tek aday, etiketi en uzun pencereden.
    etiketler = {c.label for c in by_type[SOURCE_RANGE]}
    assert etiketler == {"HIGH_60", "LOW_60"}
    assert all(c.weight == 0.7 and c.index is not None for c in by_type[SOURCE_RANGE])
    assert [(c.price, c.weight, c.confirmed) for c in by_type[SOURCE_ROUND]] == [(100.0, 0.2, True)]
    alt, ust = 110.0 - 12 * seri[-1], 110.0 + 12 * seri[-1]
    assert all(alt <= c.price <= ust for c in cands)
    assert candidates(bars, [None] * len(bars), 110.0, []) == []


def test_developing_aday_yarim_agirlik_ve_onaysiz():
    bars = mumlar(disli(2) + [122.0, 124.0, 126.0, 128.0])
    cands = candidates(bars, atr(bars, 14), 120.0, [])
    son = [c for c in cands if c.index == len(bars) - 1]
    assert {c.source_type for c in son} == {SOURCE_SWING, SOURCE_RANGE}
    assert all(not c.confirmed for c in son)
    assert {c.label: c.weight for c in son} == {"SWING_HIGH": 0.5, "HIGH_20": 0.7 * 0.5}


def test_uc_deger_pencereleri_farkli_mumdaysa_ayri_aday():
    bars = mumlar(disli(2) + [110.0 + (i % 3) for i in range(30)])
    cands = candidates(bars, atr(bars, 14), 110.0, [])
    etiketler = {c.label for c in cands if c.source_type == SOURCE_RANGE}
    assert {"HIGH_20", "HIGH_60", "LOW_20", "LOW_60"} <= etiketler


# --- kümeleme ------------------------------------------------------------------

def test_kumeleme_tam_baglanti_tavani():
    a = 1.0                                   # tol 0,5 · span 1,0
    params = LevelParams()
    esit = [Candidate(p, SOURCE_PIVOT, f"p{i}", 1.0, None, True, None)
            for i, p in enumerate([0.0, 0.45, 0.9, 1.35, 1.8])]
    kumeler = cluster_zones(esit, a, params)
    # Tek bağlantı 5'ini zincirlerdi; merkez kuralı 3 küme verir.
    assert [tuple(m.price for m in g) for g in kumeler] == [(0.0, 0.45), (0.9, 1.35), (1.8,)]
    for g in kumeler:
        merkez = sum(m.price * m.weight for m in g) / sum(m.weight for m in g)
        assert max(m.price for m in g) - min(m.price for m in g) <= params.cluster_span_atr * a
        assert all(abs(m.price - merkez) <= params.cluster_atr_factor * a for m in g)
    # Ağır üyeler merkezi sürükler: yalnız merkez kuralı 1,15 ATR'lik zincire izin verir,
    # span tavanı keser.
    zincir = [Candidate(0.0, SOURCE_ROUND, "R", 0.1, None, True, None),
              Candidate(0.5, SOURCE_PIVOT, "a", 1.0, None, True, None),
              Candidate(0.95, SOURCE_PIVOT, "b", 1.0, None, True, None),
              Candidate(1.15, SOURCE_PIVOT, "c", 1.0, None, True, None)]
    assert [len(g) for g in cluster_zones(zincir, a, params)] == [3, 1]
    assert [len(g) for g in cluster_zones(zincir, a, replace(params, cluster_span_atr=10.0))] == [4]


def test_kumeleme_fiyat_sirali_ve_belirlenimci():
    cands = [Candidate(p, SOURCE_PIVOT, f"p{i}", 1.0, None, True, None)
             for i, p in enumerate([5.0, 1.0, 1.2, 9.0, 0.9])]
    kumeler = cluster_zones(cands, 1.0)
    assert [tuple(m.price for m in g) for g in kumeler] == [(0.9, 1.0, 1.2), (5.0,), (9.0,)]
    assert cluster_zones(list(reversed(cands)), 1.0) == kumeler
    assert cluster_zones([], 1.0) == []


# --- temas olayları ------------------------------------------------------------

def test_ardisik_temaslar_tek_olay():
    kapanis = [105.0] * 12
    kapanis[3:6] = [101.0, 101.0, 101.0]
    bars = mumlar(kapanis)
    olaylar = touch_events(bars, sabit_atr(12), ZONE_LOW, ZONE_HIGH)
    assert [(e.start, e.end, e.side, e.klass, e.rejection) for e in olaylar] == [
        (3, 5, SIDE_ABOVE, CLASS_REJECTION, 3.0)]   # 4,5 ATR uzaklaşma 3'e kırpılır
    assert olaylar[0].date == BASLANGIC + timedelta(days=5)


def test_yeni_olay_arada_uzak_kapanis_ister():
    def seri(ara):
        kapanis = [105.0] * 16
        kapanis[3] = kapanis[9] = 100.9
        kapanis[4:9] = [ara] * 5
        return mumlar(kapanis, r=0.3)
    # Arada 105: bölgeden 1 ATR'den uzak kapanış → iki olay.
    uzak = touch_events(seri(105.0), sabit_atr(16), ZONE_LOW, ZONE_HIGH)
    assert [(e.start, e.end) for e in uzak] == [(3, 3), (9, 9)]
    # Arada 101,3: temas etmez ama uzak da değil (konsolidasyon) → tek olay.
    yakin = touch_events(seri(101.3), sabit_atr(16), ZONE_LOW, ZONE_HIGH)
    assert [(e.start, e.end) for e in yakin] == [(3, 9)]


def test_dislanan_mum_olayin_tamamini_dusurur():
    kapanis = [105.0] * 12
    kapanis[3:6] = [101.0, 101.0, 101.0]
    bars = mumlar(kapanis)
    assert touch_events(bars, sabit_atr(12), ZONE_LOW, ZONE_HIGH, exclude=frozenset({4})) == []
    assert len(touch_events(bars, sabit_atr(12), ZONE_LOW, ZONE_HIGH, exclude=frozenset({7}))) == 1


def test_fitil_temasi_sonra_uzaklasma_rejection_1():
    bars = mumlar([103.0] * 10, r=0.3)
    bars[5] = Candle(date=bars[5].date, high=103.3, low=100.7, close=103.0)   # yalnız fitil
    for i in (6, 7, 8):
        bars[i] = Candle(date=bars[i].date, high=101.8, low=101.2, close=ZONE_HIGH + 1.0)
    olaylar = touch_events(bars, sabit_atr(10), ZONE_LOW, ZONE_HIGH)
    assert len(olaylar) == 1
    e = olaylar[0]
    assert (e.start, e.end, e.side, e.klass) == (5, 5, SIDE_ABOVE, CLASS_REJECTION)
    assert e.rejection == 1.0


def test_kapanisla_gecis_break():
    kapanis = [103.0] * 10
    kapanis[5] = 101.0
    kapanis[6:10] = [98.9, 98.8, 98.7, 98.7]      # 0,6 ATR aşım, sonra hep ötede
    olaylar = touch_events(mumlar(kapanis, r=0.3), sabit_atr(10), ZONE_LOW, ZONE_HIGH)
    assert [(e.start, e.end, e.klass, e.rejection) for e in olaylar] == [(5, 5, CLASS_BREAK, 0.0)]


def test_teyitsiz_gecis_neutral():
    kapanis = [103.0] * 10
    kapanis[5] = 101.0
    kapanis[8] = 98.8                             # pencerenin son mumunda tek geçiş
    olaylar = touch_events(mumlar(kapanis, r=0.3), sabit_atr(10), ZONE_LOW, ZONE_HIGH)
    assert [(e.klass, e.rejection) for e in olaylar] == [(CLASS_NEUTRAL, 0.0)]


def test_son_mumlardaki_temas_pending():
    kapanis = [103.0] * 10
    kapanis[8] = 101.0
    olaylar = touch_events(mumlar(kapanis, r=0.3), sabit_atr(10), ZONE_LOW, ZONE_HIGH)
    assert [(e.start, e.klass, e.rejection) for e in olaylar] == [(8, CLASS_PENDING, None)]
    kapanis[8], kapanis[6] = 103.0, 101.0         # 6 + 3 = 9 = son mum → sınıflanır
    olaylar = touch_events(mumlar(kapanis, r=0.3), sabit_atr(10), ZONE_LOW, ZONE_HIGH)
    assert olaylar[0].klass != CLASS_PENDING


def test_asagidan_yaklasma_break_yukari():
    kapanis = [97.0] * 10
    kapanis[5] = 99.0                              # high 99,3 ≥ 99,25 → temas
    kapanis[6:10] = [101.1, 101.2, 101.3, 101.3]
    olaylar = touch_events(mumlar(kapanis, r=0.3), sabit_atr(10), ZONE_LOW, ZONE_HIGH)
    assert [(e.side, e.klass) for e in olaylar] == [(SIDE_BELOW, CLASS_BREAK)]


def test_olay_agirligi_yari_omurle_eskir():
    kapanis = [105.0] * 100
    kapanis[9] = 101.0                             # yaş = 99 − 9 = 90 gün → 0,5
    olaylar = touch_events(mumlar(kapanis), sabit_atr(100), ZONE_LOW, ZONE_HIGH)
    assert olaylar[0].weight == pytest.approx(0.5)
    yavas = touch_events(mumlar(kapanis), sabit_atr(100), ZONE_LOW, ZONE_HIGH,
                         params=LevelParams(recency_half_life_days=1e9))
    assert yavas[0].weight == pytest.approx(1.0)


def test_isinma_mumlari_temas_sayilmaz():
    kapanis = [105.0] * 20
    kapanis[2] = kapanis[16] = 101.0
    seri = [None] * 14 + [1.0] * 6
    olaylar = touch_events(mumlar(kapanis), seri, ZONE_LOW, ZONE_HIGH)
    assert [e.start for e in olaylar] == [16]


# --- güç -----------------------------------------------------------------------

def test_uc_kez_tutan_bir_kez_tutandan_guclu():
    uc, _ = score_zone([olay(CLASS_REJECTION, 1.0, 2.0, e) for e in (10, 20, 30)], [SWING], last_index=100)
    bir, _ = score_zone([olay(CLASS_REJECTION, 1.0, 2.0, 30)], [SWING], last_index=100)
    assert uc > bir


def test_hold_laplace_bir_kirilim():
    olaylar = [olay(CLASS_REJECTION, 1.0, 2.0, 10), olay(CLASS_BREAK, 1.0, 0.0, 20),
               olay(CLASS_NEUTRAL, 1.0, 0.0, 30)]
    _, parcalar = score_zone(olaylar, [SWING], last_index=100)
    assert parcalar["hold"] == pytest.approx((2 + 1) / (3 + 2))
    assert parcalar["break_factor"] == 1.0                    # son olay kırılım değil
    assert parcalar["rejection"] == pytest.approx((2.0 / 3.0) / 3)
    assert parcalar["touch"] == pytest.approx(1 - math.exp(-3 / 2.0))
    # PENDING temas sayar, sınıflamaya girmez.
    _, bekleyen = score_zone(olaylar + [olay(CLASS_PENDING, 1.0, None, 40)], [SWING], last_index=100)
    assert bekleyen["hold"] == pytest.approx(3 / 5)
    assert bekleyen["touch"] > parcalar["touch"]


def test_break_factor_taze_kirilimda_yarilanir():
    olaylar = [olay(CLASS_REJECTION, 1.0, 2.0, 10), olay(CLASS_NEUTRAL, 1.0, 0.0, 20),
               olay(CLASS_BREAK, 1.0, 0.0, 30)]
    guc, parcalar = score_zone(olaylar, [SWING], last_index=100)
    assert parcalar["break_factor"] == pytest.approx(0.5)
    assert guc == round(100 * parcalar["base"] * 0.5)
    eski = olaylar[:2] + [olay(CLASS_BREAK, 0.25, 0.0, 30)]
    assert score_zone(eski, [SWING], last_index=100)[1]["break_factor"] == pytest.approx(0.875)


def test_400_gunluk_temas_10_gunlukten_zayif():
    kapanis = [110.0] * 420
    bars = mumlar(kapanis, r=0.3)
    bars[15] = Candle(date=bars[15].date, high=110.3, low=100.7, close=110.0)
    bars[405] = Candle(date=bars[405].date, high=119.3, low=109.7, close=110.0)
    seri = sabit_atr(420)
    eski = touch_events(bars, seri, ZONE_LOW, ZONE_HIGH)      # 15: aşağı fitil
    yeni = touch_events(bars, seri, 119.5, 120.5)             # 405: yukarı fitil
    assert [e.klass for e in eski] == [e.klass for e in yeni] == [CLASS_REJECTION]
    assert eski[0].weight == pytest.approx(0.5 ** (404 / 90))
    assert yeni[0].weight == pytest.approx(0.5 ** (14 / 90))
    guc_eski, _ = score_zone(eski, [SWING], last_index=419)
    guc_yeni, _ = score_zone(yeni, [replace(SWING, price=120.0)], last_index=419)
    assert guc_yeni > guc_eski


def test_iki_kaynak_turu_birden_guclu():
    olaylar = [olay(CLASS_REJECTION, 1.0, 2.0, 30)]
    tek, _ = score_zone(olaylar, [SWING], last_index=100)
    cift, parcalar = score_zone(olaylar, [SWING, PIVOT], last_index=100)
    assert cift > tek
    assert parcalar["confluence"] == pytest.approx(1 - math.exp(-1 / 1.5))


def test_test_edilmemis_bolge_esigin_altinda():
    """Temas yokken tavan: hold 0,5 · confluence(4 tür) · source 1 → 28 < 30."""
    params = LevelParams()
    uyeler = [SWING, PIVOT, RANGE, ROUND]
    en_yuksek = 0
    for k in range(1, 5):
        for secim in combinations(uyeler, k):
            guc, parcalar = score_zone([], list(secim), last_index=100, params=params)
            assert parcalar["touch"] == 0.0 and parcalar["recency"] == 0.0
            assert parcalar["hold"] == 0.5
            assert guc < params.min_strength
            en_yuksek = max(en_yuksek, guc)
    assert en_yuksek == 28
    # Tek istisna: son mumda DEVELOPING üye tazeliği 1 sayar → 38. Böyle bir
    # bölge yalnız DEVELOPING üyelerden oluşuyorsa zaten onaysızdır ve hedef
    # olamaz; onaylı üyeyle karışıksa eşik üstü olabilir — belgelenmiş sınır.
    gelisen = replace(SWING, confirmed=False, weight=0.5, index=100)
    guc, parcalar = score_zone([], [gelisen, PIVOT, RANGE, ROUND], last_index=100, params=params)
    assert parcalar["recency"] == 1.0 and guc == 38


def test_guc_etiketleri():
    assert strength_label(67) == LABEL_STRONG
    assert strength_label(66) == LABEL_MODERATE
    assert strength_label(34) == LABEL_MODERATE
    assert strength_label(33) == LABEL_WEAK
    assert strength_label(0) == LABEL_WEAK


# --- analyze_levels -------------------------------------------------------------

def test_testere_dip_ve_tepe_bolgeleri_secilir():
    lv = analyze_levels(mumlar(disli(10)), 110.0)
    assert lv.status == STATUS_OK and lv.atr == pytest.approx(3.0, abs=0.05)
    dip, tepe = bolge(lv, 99.0), bolge(lv, 121.0)
    assert dip.kind == KIND_SUPPORT and tepe.kind == KIND_RESISTANCE
    # 9 dip döngüsünden ilki köken (test değil), gerisi dönüşle biten test.
    assert dip.touches == 8 and dip.rejections == 8 and dip.breaks == 0
    assert dip.label == LABEL_STRONG and tepe.label == LABEL_STRONG
    assert {SOURCE_SWING, SOURCE_RANGE, SOURCE_ROUND} == set(dip.source_types)
    assert (lv.nearest_support, lv.nearest_resistance) == (dip.id, tepe.id)
    assert lv.side_status == {"support": SIDE_OK, "resistance": SIDE_OK}
    assert lv.testing == () and lv.weakest_ignored is None
    assert lv.cluster_tolerance == pytest.approx(0.5 * lv.atr)
    assert lv.margin_usd == pytest.approx(0.25 * lv.atr)
    assert lv.scan_range == pytest.approx((110 - 12 * lv.atr, 110 + 12 * lv.atr))


def test_referans_bolgenin_icindeyse_test_ediliyor_hedef_degil():
    lv = analyze_levels(mumlar(disli(10)), 99.3)
    dip = bolge(lv, 99.0)
    assert dip.testing and lv.testing == (dip.id,)
    assert lv.nearest_support is None and lv.side_status["support"] == NO_VALID_SUPPORT
    assert lv.nearest_resistance == bolge(lv, 121.0).id
    assert dip.strength >= lv.min_strength      # güçlü ama yine de hedef değil


def test_asagida_yalniz_esik_alti_bolge_varsa_weakest_ignored():
    lv = analyze_levels(mumlar(disli(10)), 96.0, pivot_levels=[("S1", 90.0)])
    assert lv.side_status["support"] == NO_VALID_SUPPORT and lv.nearest_support is None
    assert lv.weakest_ignored is not None and set(lv.weakest_ignored) == {"support"}
    zayif = lv.weakest_ignored["support"]
    assert zayif["name"] == "S1" and zayif["strength"] < lv.min_strength
    assert zayif["kind"] == KIND_SUPPORT and zayif["touches"] == 0
    assert lv.nearest_resistance == bolge(lv, 99.0).id
    assert lv.next_resistance == bolge(lv, 121.0).id


def test_developing_bolge_asla_hedef_ya_da_test_degil():
    bars = mumlar(disli(5) + [102.0 + 2 * k for k in range(2, 16)])
    lv = analyze_levels(bars, 120.0)
    gelisen = [z for z in lv.zones if not z.confirmed]
    assert len(gelisen) == 1 and gelisen[0].mid == pytest.approx(133.0)
    # Test edilmemiş ama tazelik 1: eşik üstü — yine de dışarıda kalmalı.
    assert gelisen[0].strength >= lv.min_strength
    assert gelisen[0].id not in (lv.nearest_resistance, lv.next_resistance) + lv.testing
    assert lv.side_status["resistance"] == NO_VALID_RESISTANCE
    assert lv.weakest_ignored is None or "resistance" not in lv.weakest_ignored
    assert bolge(lv, 121.0).testing and lv.nearest_support == bolge(lv, 101.0).id


def test_duz_piyasa_flat_market():
    bars = [Candle(date=BASLANGIC + timedelta(days=i), high=100.0, low=100.0, close=100.0) for i in range(40)]
    lv = analyze_levels(bars, 100.0)
    assert lv.status == STATUS_FLAT_MARKET and lv.zones == () and lv.atr == 0.0
    assert lv.as_of == bars[-1].date
    assert lv.side_status == {"support": NO_VALID_SUPPORT, "resistance": NO_VALID_RESISTANCE}


def test_34_mum_insufficient_data():
    kapanis = disli(2)
    az = analyze_levels(mumlar(kapanis[:34]), 110.0)
    assert az.status == STATUS_INSUFFICIENT_DATA and az.zones == () and az.atr is None
    assert az.as_of == BASLANGIC + timedelta(days=33)
    assert analyze_levels(mumlar(kapanis[:35]), 110.0).status == STATUS_OK
    assert analyze_levels([], 110.0).status == STATUS_INSUFFICIENT_DATA
    with pytest.raises(ValueError):
        analyze_levels(mumlar(kapanis), 0.0)


def test_cerceve_degismezligi():
    """Spot ↔ vadeli farkı (×1,0095) güç, etiket ve yüzde mesafeyi değiştirmez.
    Yuvarlak sayılar tanım gereği çerçeveye bağlı; bu testte kapalı."""
    k = 1.0095
    params = LevelParams(round_step=0.0)
    kapanis = gurultulu_disli(10)
    pivotlar = [("P", 110.0), ("R1", 125.0)]
    a = analyze_levels(mumlar(kapanis), 110.0, pivot_levels=pivotlar, sigma=0.012, params=params)
    b = analyze_levels(mumlar([c * k for c in kapanis], r=k), 110.0 * k,
                       pivot_levels=[(n, v * k) for n, v in pivotlar], sigma=0.012, params=params)
    assert a.status == b.status == STATUS_OK and len(a.zones) == len(b.zones) >= 3
    for za, zb in zip(a.zones, b.zones):
        assert (za.strength, za.label, za.kind, za.touches, za.rejections, za.breaks, za.name) == \
            (zb.strength, zb.label, zb.kind, zb.touches, zb.rejections, zb.breaks, zb.name)
        assert za.distance_pct == pytest.approx(zb.distance_pct, rel=1e-9)
        assert za.distance_atr == pytest.approx(zb.distance_atr, rel=1e-9)
        assert za.distance_sigma == pytest.approx(zb.distance_sigma, rel=1e-9)
        assert za.distance_usd * k == pytest.approx(zb.distance_usd)
        assert za.testing == zb.testing
    assert (a.nearest_support is None) == (b.nearest_support is None)
    assert a.side_status == b.side_status


def test_belirlenimci():
    bars = mumlar(gurultulu_disli(10))
    assert analyze_levels(bars, 110.0, pivot_levels=[("P", 110.0)]) == \
        analyze_levels(list(bars), 110.0, pivot_levels=[("P", 110.0)])


def test_on_ek_ileri_bakmaz():
    bars = mumlar(gurultulu_disli(10))
    for t in (50, 120, 200):
        on_ek = bars[:t]
        lv = analyze_levels(on_ek, 110.0)
        assert lv == analyze_levels(list(on_ek), 110.0)
        assert lv.as_of == on_ek[-1].date
        for z in lv.zones:
            assert z.last_touch is None or z.last_touch <= lv.as_of
            assert all(c.index is None or c.index < t for c in z.sources)
            olaylar = touch_events(on_ek, atr(on_ek, 14), z.low, z.high)
            assert all(e.start <= e.end < t for e in olaylar)


def test_bolge_kimlikleri_tekil_ve_carpismada_ekli():
    bars = [Candle(date=BASLANGIC + timedelta(days=i), high=100.05, low=99.95, close=100.0) for i in range(40)]
    lv = analyze_levels(bars, 100.35, pivot_levels=[("P1", 100.3), ("P2", 100.4)])
    assert lv.status == STATUS_OK
    kimlikler = [z.id for z in lv.zones]
    assert len(set(kimlikler)) == len(kimlikler) == 4
    assert set(kimlikler) == {"z-100", "z-100-2", "z-100-3", "z-100-4"}
    assert [z.strength for z in lv.zones] == sorted((z.strength for z in lv.zones), reverse=True)


def test_mesafe_alanlari():
    lv = analyze_levels(mumlar(disli(10)), 110.0, sigma=0.01)
    for z in lv.zones:
        assert z.distance_usd == pytest.approx(z.mid - 110.0)
        assert z.distance_pct == pytest.approx(z.mid / 110.0 - 1)
        assert z.distance_atr == pytest.approx((z.mid - 110.0) / lv.atr)
        assert z.distance_sigma == pytest.approx((z.mid - 110.0) / (110.0 * 0.01))
        assert z.kind == (KIND_SUPPORT if z.mid < 110.0 else KIND_RESISTANCE)
        assert z.low <= z.mid <= z.high and z.high - z.low >= 2 * 0.25 * lv.atr - 1e-9
        assert set(z.components) >= {"touch", "rejection", "hold", "confluence", "recency", "source", "base", "break_factor"}
    assert all(z.distance_sigma is None for z in analyze_levels(mumlar(disli(10)), 110.0).zones)


def test_max_zones_kirpar():
    lv = analyze_levels(mumlar(gurultulu_disli(10)), 110.0, params=LevelParams(max_zones=2))
    assert len(lv.zones) == 2
    assert lv.zones[0].strength >= lv.zones[1].strength


def test_fixture_xau_gunluk_smoke():
    veri = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bars, kalite = normalize_daily(veri["points"])
    assert kalite.status == STATUS_OK and len(bars) == 1257
    sureler = []
    for _ in range(3):
        basla = time.perf_counter()
        lv = analyze_levels(bars, 4476.6, pivot_levels=HAFTALIK_KLASIK)
        sureler.append(time.perf_counter() - basla)
    assert min(sureler) < 0.25, f"en iyi süre {min(sureler) * 1000:.1f} ms"
    assert lv.status == STATUS_OK and lv.as_of == date(2026, 9, 4)
    assert lv.zones and len(lv.zones) <= LevelParams().max_zones
    assert len({z.id for z in lv.zones}) == len(lv.zones)
    for yan, yakin in (("support", lv.nearest_support), ("resistance", lv.nearest_resistance)):
        assert (yakin is not None) == (lv.side_status[yan] == SIDE_OK)
    print(f"\nfixture: atr={lv.atr:.2f} zones={len(lv.zones)} best={min(sureler) * 1000:.1f} ms")
    for z in lv.zones[:8]:
        print(f"  {z.id:>9} mid={z.mid:8.1f} {z.kind:<10} {z.strength:3d} {z.label:<8} "
              f"touch={z.touches} rej={z.rejections} brk={z.breaks} src={[c.label for c in z.sources]}")
    print(f"  nearest_support={lv.nearest_support} next={lv.next_support} "
          f"nearest_resistance={lv.nearest_resistance} next={lv.next_resistance} "
          f"testing={lv.testing} side={lv.side_status}")
