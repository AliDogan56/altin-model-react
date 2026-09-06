"""Günlük bileşik momentum (`technical/momentum_daily.py`).

Kritik sözleşmeler: skor ölçekten bağımsızdır (bütün bileşenler oran),
ısınmadaki bileşen sıfırla doldurulmaz **düşürülür**, düz piyasa "nötr" değil
"ölçülemez"dir (FLAT_MARKET) ve seri **nedenseldir** — t'deki skor yalnız
t ve öncesini görür, bu yüzden delta / ivme / trend etiketleri geleceğe bakmaz.

Sentetik seriler tohumlu `random.Random` ile üretilir; Mersenne Twister'ın
`gauss` dizisi CPython sürümleri arasında sabittir, testler belirlenimcidir.
"""
import json
import math
import random
import statistics
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from app.services.technical import candles
from app.services.technical.indicators import IndicatorParams
from app.services.technical.momentum_daily import (
    COMPONENTS, MomentumDaily, MomentumParams, label_direction, label_note,
    label_strength, label_trend, momentum_daily, score_series,
)

FIXTURE = Path(__file__).parent / "fixtures" / "xau_daily_20260906.json"


@dataclass(frozen=True)
class Mum:
    high: float
    low: float
    close: float


def mumlar(kapanislar, rng=None, aralik=0.004):
    """Kapanış etrafında aralıklı mumlar; `rng` verilirse gün içi aralık
    0,5–1,5 kat arasında rastgele (ATR sabit kalmasın diye)."""
    out = []
    for c in kapanislar:
        genislik = c * aralik * ((0.5 + rng.random()) if rng else 1.0)
        out.append(Mum(c + genislik / 2, c - genislik / 2, c))
    return out


def rampa(n, adim, gurultu, tohum=20260906):
    """Sabit log adımlı yükseliş + Gauss gürültüsü."""
    rng = random.Random(tohum)
    kapanislar = [100.0]
    for _ in range(n - 1):
        kapanislar.append(kapanislar[-1] * math.exp(adim + rng.gauss(0.0, gurultu)))
    return mumlar(kapanislar, random.Random(tohum + 1))


def yuruyus(n, tohum, oynaklik=0.006):
    """Sürüklenmesiz log rastgele yürüyüş; 100 çevresinde kalır."""
    rng = random.Random(tohum)
    kapanislar = [100.0]
    for _ in range(n - 1):
        kapanislar.append(kapanislar[-1] * math.exp(rng.gauss(0.0, oynaklik)))
    return mumlar(kapanislar, random.Random(tohum + 100))


def zikzak(n, seviye=100.0, genlik=0.05):
    """Dönemi 2 olan zikzak: hiçbir ufukta yön bilgisi taşımaz ama σ > 0."""
    return [Mum(seviye + e + 0.5, seviye + e - 0.5, seviye + e)
            for e in (genlik if i % 2 == 0 else -genlik for i in range(n))]


def duz(n, seviye=100.0):
    return [Mum(seviye, seviye, seviye) for _ in range(n)]


def ayna(bars):
    """İlk kapanış etrafında yansıma: m = 2·p₀ − p; yüksek ile düşük yer değişir."""
    p0 = bars[0].close
    return [Mum(2 * p0 - b.low, 2 * p0 - b.high, 2 * p0 - b.close) for b in bars]


@pytest.fixture(scope="module")
def fixture_mumlari():
    noktalar = json.loads(FIXTURE.read_text(encoding="utf-8"))["points"]
    mumlar_, kalite = candles.normalize_daily(noktalar)
    assert kalite.status == candles.STATUS_OK and len(mumlar_) == 1257
    return mumlar_


# --- parametreler ---------------------------------------------------------------

def test_agirliklar_bire_toplanmazsa_hata():
    with pytest.raises(ValueError):
        MomentumParams(weights=(("velocity", 0.5), ("drift", 0.4)))
    with pytest.raises(ValueError):
        MomentumParams(weights=(("velocity", 0.5), ("hacim", 0.5)))
    # 1e-9 payı: kayan nokta toplamı tam 1 vermeyebilir.
    MomentumParams(weights=(("velocity", 1 / 3), ("drift", 1 / 3), ("rsi", 1 / 3)))
    assert math.isclose(sum(MomentumParams().weight_map().values()), 1.0)


def test_varsayilan_agirliklar_tasarim_tablosu():
    assert MomentumParams().weight_map() == {
        "velocity": 0.25, "drift": 0.20, "rsi": 0.15, "macd": 0.15, "adx": 0.15, "ma": 0.10}
    assert tuple(MomentumParams().weight_map()) == COMPONENTS


# --- uç davranışlar -------------------------------------------------------------

def test_testere_seri_50_civari_notr_zayif_sabit():
    """Zikzakta 10 ve 20 günlük getiri tam sıfır, RSI ≈ 50; skor 50 çevresinde
    salınır. Bileşenler çekiştiği (uyum < 0,5) için NEUTRAL "CONFLICTING" notu alır."""
    sonuc = momentum_daily(zikzak(120))
    assert sonuc.status == "OK"
    assert abs(sonuc.score - 50) <= 3
    assert (sonuc.direction, sonuc.strength, sonuc.trend) == ("NEUTRAL", "WEAK", "STABLE")
    assert sonuc.components["velocity"] == 0.0 and sonuc.components["drift"] == 0.0
    assert sonuc.note == "CONFLICTING" and sonuc.agreement < 0.5


def test_gercekten_duz_seri_flat_market():
    """high = low = close: σ = 0 ve ATR = 0. Bölme tanımsız; "nötr 50" değil
    FLAT_MARKET ve skor None — serinin her indeksinde."""
    sonuc = momentum_daily(duz(120))
    assert sonuc.status == "FLAT_MARKET"
    assert sonuc.score is None and sonuc.direction is None and sonuc.components == {}
    assert sonuc.sigma == 0.0 and sonuc.atr == 0.0
    assert set(score_series(duz(120))) == {None}


def test_yetersiz_veri():
    assert momentum_daily([]).status == "INSUFFICIENT_DATA"
    assert momentum_daily([]).date is None
    kisa = momentum_daily(rampa(34, 0.003, 0.001))
    assert kisa.status == "INSUFFICIENT_DATA" and kisa.score is None and kisa.history == ()
    assert momentum_daily(rampa(35, 0.003, 0.001)).status == "OK"
    # Seride de aynı kapı: ilk 34 indeks None, 35. mumdan itibaren skor var.
    seri = score_series(rampa(60, 0.003, 0.001))
    assert seri[:34] == [None] * 34 and None not in seri[34:]


def test_rampa_guclu_yukari():
    sonuc = momentum_daily(rampa(150, 0.003, 0.001))
    assert sonuc.status == "OK"
    assert sonuc.score > 75
    assert (sonuc.direction, sonuc.strength) == ("UP", "STRONG")
    assert sonuc.note is None
    assert all(sonuc.components[name] > 0 for name in ("velocity", "drift", "rsi", "adx", "ma"))


def test_bes_kat_gurultu_kanaati_azaltir():
    """Aynı sürüklenme, beş kat gürültü: hareket σ biriminde küçülür, skor
    50'ye yaklaşır. Momentum "ne kadar yükseldi" değil "gürültüye göre ne
    kadar tek yönlü" sorusudur."""
    sakin = momentum_daily(rampa(150, 0.003, 0.001))
    calkantili = momentum_daily(rampa(150, 0.003, 0.005))
    assert abs(calkantili.score - 50) < abs(sakin.score - 50)
    assert abs(calkantili.components["velocity"]) < abs(sakin.components["velocity"])
    assert abs(calkantili.components["drift"]) < abs(sakin.components["drift"])


# --- değişmezler ----------------------------------------------------------------

def test_olcek_degismezligi(fixture_mumlari):
    """Bütün bileşenler oran: fiyatı 1,0095 ile çarpmak hiçbir skoru değiştirmez."""
    olcekli = [candles.Candle(c.date, c.high * 1.0095, c.low * 1.0095, c.close * 1.0095)
               for c in fixture_mumlari]
    assert score_series(olcekli) == score_series(fixture_mumlari)
    assert momentum_daily(olcekli).score == momentum_daily(fixture_mumlari).score


@pytest.mark.parametrize("tohum", [11, 12, 13])
def test_ayna_simetrisi(tohum):
    """m = 2·p₀ − p için skor ≈ 100 − skor, ±3.

    Tam değil, çünkü yansıma **toplamsal**, hız ve sürüklenme ise log getiri:
    ln(m_t / m_{t−k}) ≠ −ln(p_t / p_{t−k}); σ da aynı sebeple birebir aynı
    değil. Wilder ailesi (RSI, ADX/DI, ATR) ile SMA ve MACD bu yansımada tam
    antisimetriktir: kazanç ↔ kayıp, +DM ↔ −DM yer değiştirir, EMA doğrusal.
    Kalan fark log/toplamsal ayrımı ve yuvarlama; ölçüldü: en çok 1 puan."""
    temel = yuruyus(300, tohum)
    assert min(b.low for b in ayna(temel)) > 0
    asil, yansima = score_series(temel), score_series(ayna(temel))
    ciftler = [(a, b) for a, b in zip(asil, yansima) if a is not None and b is not None]
    assert len(ciftler) > 200
    assert all(abs(a + b - 100) <= 3 for a, b in ciftler)


def test_isinmada_eksik_bilesen_dusurulur_agirlik_dagitilir():
    """41 mumda SMA50 yok ama RSI / MACD / ADX / σ var: `ma` sözlükte hiç
    yok (0 yazılmaz), kalan beş ağırlık 1'e yeniden dağıtılır, skor var."""
    seri = rampa(150, 0.003, 0.001)
    sonuc = momentum_daily(seri[:41])
    assert sonuc.status == "OK" and sonuc.score is not None
    assert set(sonuc.components) == {"velocity", "drift", "rsi", "macd", "adx"}
    assert "ma" not in sonuc.weights
    assert math.isclose(sum(sonuc.weights.values()), 1.0, abs_tol=1e-12)
    assert math.isclose(sonuc.weights["velocity"], 0.25 / 0.90)
    # 50. mumda SMA50 doğar, altı bileşen de tabloda ve ağırlıklar özgün değerler.
    tam = momentum_daily(seri[:50])
    assert set(tam.components) == set(COMPONENTS)
    assert tam.weights == MomentumParams().weight_map()


def test_ivmelenme_sonra_durma_trend_etiketleri():
    """80 gün yatay, 15 gün +%0,6/gün, sonra yatay. Rampanın başında skor
    hızla büyür (STRENGTHENING), doygunlukta STABLE, durmanın birkaç gün
    sonrasında 10 günlük pencere rampadan çıkarken WEAKENING."""
    rng = random.Random(5)
    kapanislar = [100.0]
    for i in range(1, 120):
        adim = 0.006 if 80 <= i < 95 else 0.0
        kapanislar.append(kapanislar[-1] * math.exp(adim + rng.gauss(0.0, 0.0015)))
    seri = mumlar(kapanislar, random.Random(6))

    def gun(t):
        return momentum_daily(seri[:t + 1])

    assert all(gun(t).trend == "STRENGTHENING" for t in (81, 83, 85))
    assert gun(93).trend == "STABLE" and gun(93).score >= 95
    durma = [gun(t) for t in (98, 100, 102, 104, 106)]
    assert all(g.trend == "WEAKENING" for g in durma)
    assert all(g.delta is not None and g.delta <= 0 for g in durma)
    # Skor durma boyunca gerçekten geriliyor.
    assert gun(106).score < gun(98).score < gun(93).score


def test_deterministik(fixture_mumlari):
    assert momentum_daily(fixture_mumlari) == momentum_daily(fixture_mumlari)
    assert score_series(fixture_mumlari) == score_series(fixture_mumlari)


@pytest.mark.parametrize("t", [35, 40, 80, 150, 300, 700, 1257])
def test_nedensellik(fixture_mumlari, t):
    """Seriyi t'de kesmek t−1'deki skoru değiştirmez; son gün raporu da aynı sayı."""
    tam = score_series(fixture_mumlari)
    kesik = fixture_mumlari[:t]
    assert score_series(kesik)[t - 1] == tam[t - 1]
    assert momentum_daily(kesik).score == tam[t - 1]


def test_delta_ve_ivme_seriden_okunur(fixture_mumlari):
    tam = score_series(fixture_mumlari)
    for t in (100, 600, 1257):
        rapor = momentum_daily(fixture_mumlari[:t])
        s0, s1, s2 = tam[t - 1], tam[t - 2], tam[t - 3]
        assert rapor.delta == s0 - s1
        assert rapor.acceleration == (s0 - s1) - (s1 - s2)
        assert rapor.trend == label_trend(s0, tam[t - 4])


def test_gecmis_en_cok_30_ve_serinin_kuyrugu(fixture_mumlari):
    rapor = momentum_daily(fixture_mumlari)
    tam = score_series(fixture_mumlari)
    assert len(rapor.history) == 30
    assert rapor.history == tuple(tam[-30:])
    assert rapor.history[-1] == rapor.score
    kisa = momentum_daily(fixture_mumlari[:40])
    assert 0 < len(kisa.history) <= 30 and None not in kisa.history
    assert momentum_daily(fixture_mumlari, MomentumParams(history=7)).history == tuple(tam[-7:])


# --- etiket sınırları ------------------------------------------------------------

def test_yon_sinirlari():
    assert label_direction(60) == "UP" and label_direction(59) == "NEUTRAL"
    assert label_direction(40) == "DOWN" and label_direction(41) == "NEUTRAL"
    assert label_direction(100) == "UP" and label_direction(0) == "DOWN"


def test_guc_sinirlari():
    assert label_strength(75) == "STRONG" and label_strength(25) == "STRONG"
    assert label_strength(74) == "MODERATE" and label_strength(26) == "MODERATE"
    assert label_strength(60) == "MODERATE" and label_strength(40) == "MODERATE"
    assert label_strength(59) == "WEAK" and label_strength(41) == "WEAK" and label_strength(50) == "WEAK"


def test_trend_ve_not_etiketleri():
    assert label_trend(63, 60) == "STRENGTHENING" and label_trend(62, 60) == "STABLE"
    assert label_trend(37, 40) == "STRENGTHENING"  # düşüş momentumu da güçlenir
    assert label_trend(57, 60) == "WEAKENING" and label_trend(None, 60) is None
    assert label_note("NEUTRAL", 0.49) == "CONFLICTING"
    assert label_note("NEUTRAL", 0.5) is None and label_note("UP", 0.1) is None
    # Eşikler parametreden: z = 1 → 73 tasarım notu, z_scale ile.
    assert round(50 + 50 * math.tanh(1 / MomentumParams().z_scale)) == 73


def test_etiketler_parametreden_okur():
    params = MomentumParams(up=55, down=45, moderate=5, strong=20, trend_delta=1)
    assert label_direction(55, params) == "UP" and label_direction(45, params) == "DOWN"
    assert label_strength(70, params) == "STRONG" and label_strength(55, params) == "MODERATE"
    assert label_trend(61, 60, params) == "STRENGTHENING"


# --- fixture -----------------------------------------------------------------------

def test_fixture_son_gun_raporu(fixture_mumlari):
    """2026-09-06 fixture'ında son mum 4 Eylül. Sayı zorlanmaz; alan sözleşmesi
    denetlenir (tasarım ~43 DOWN WEAK tahmin etmişti, ölçülen 59 NEUTRAL WEAK)."""
    rapor = momentum_daily(fixture_mumlari)
    assert isinstance(rapor, MomentumDaily)
    assert rapor.status == "OK"
    assert rapor.date == date(2026, 9, 4)
    assert 0 <= rapor.score <= 100
    assert rapor.direction == label_direction(rapor.score)
    assert rapor.strength == label_strength(rapor.score)
    assert rapor.trend in {"STRENGTHENING", "WEAKENING", "STABLE"}
    assert 0.0 <= rapor.agreement <= 1.0
    assert set(rapor.components) == set(COMPONENTS)
    assert rapor.weights == MomentumParams().weight_map() and rapor.z_scale == 2.0
    assert rapor.sigma > 0 and rapor.atr > 0
    assert rapor.score == round(50 + 50 * math.tanh(rapor.z / rapor.z_scale))
    assert rapor.note in {None, "CONFLICTING"}
    assert all(math.isfinite(v) for v in rapor.components.values())


def test_fixture_serisi_dolu_ve_sinirlarda(fixture_mumlari):
    """1257 mumun ilk 34'ü ısınma, kalan 1223'ün hepsi skorlu ve 0–100 içinde;
    skor sabit değil (tasarım sd ≈ 15 istiyor — ölçülen değer raporda, burada
    yalnız "değişkenlik var" denetlenir)."""
    seri = score_series(fixture_mumlari)
    assert len(seri) == 1257 and seri[:34] == [None] * 34
    skorlar = [s for s in seri[34:] if s is not None]
    assert len(skorlar) == 1223
    assert all(0 <= s <= 100 for s in skorlar)
    assert statistics.stdev(skorlar) > 5


def test_gosterge_parametreleri_gecirilir(fixture_mumlari):
    """Farklı RSI/ATR/MACD periyodu bileşenleri değiştirir; bileşen kümesi aynı."""
    ozel = IndicatorParams(rsi_period=7, atr_period=7, macd_fast=5, macd_slow=13, macd_signal=4)
    varsayilan = momentum_daily(fixture_mumlari)
    farkli = momentum_daily(fixture_mumlari, indicator_params=ozel)
    assert farkli.status == "OK" and set(farkli.components) == set(COMPONENTS)
    assert farkli.components["rsi"] != varsayilan.components["rsi"]
    assert farkli.components["macd"] != varsayilan.components["macd"]
    # σ ve hız gösterge parametrelerinden bağımsız.
    assert farkli.sigma == varsayilan.sigma
    assert farkli.components["velocity"] == varsayilan.components["velocity"]
