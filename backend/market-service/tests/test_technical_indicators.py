"""Wilder standardındaki günlük göstergeler.

Referans değerler yayınlanmış örneklerden (StockCharts RSI çalışma sayfası)
ya da testin içinde açık aritmetikle elle hesaplanmış küçük serilerden gelir.
Kritik sözleşme: düz seri **nötr** okunur (RSI 50, stokastik 50, Williams −50,
CCI 0, ADX 0), ısınma uzunlukları kesindir ve seri girdiyle hizalıdır.
"""
import json
import math
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.services.technical.indicators import (
    IndicatorParams, IndicatorReading, IndicatorState, adx, atr, cci, ema,
    latest_indicators, macd, moving_average_table, moving_averages, roc, rsi,
    sma, stochastic, true_range, williams_r, wilder_smooth,
)

FIXTURE = Path(__file__).parent / "fixtures" / "xau_daily_20260906.json"


@dataclass(frozen=True)
class Mum:
    high: float
    low: float
    close: float


def mumlar(kapanislar, aralik=1.0):
    """Kapanış etrafında simetrik aralıklı mumlar; ardışık kapanışlar aralığın
    içinde kaldığı sürece TR = high − low."""
    return [Mum(c + aralik / 2, c - aralik / 2, c) for c in kapanislar]


def duz(n, seviye=100.0):
    """Gerçekten düz: aralık da sıfır (high = low = close)."""
    return [Mum(seviye, seviye, seviye) for _ in range(n)]


def yukselen(n, baslangic=100.0, adim=1.0):
    return [Mum(baslangic + adim * i + 1.0, baslangic + adim * i, baslangic + adim * i + 0.5)
            for i in range(n)]


def disli(n):
    return [Mum(101.0, 99.0, 100.0) if i % 2 == 0 else Mum(102.0, 100.0, 101.0) for i in range(n)]


def ilk_gecerli(seri):
    return next((i for i, v in enumerate(seri) if v is not None), None)


def fixture_mumlari():
    noktalar = json.loads(FIXTURE.read_text())["points"]
    return [Mum(float(p["h"]), float(p["l"]), float(p["c"])) for p in noktalar]


# --- temel yumuşatmalar -------------------------------------------------------

def test_sma_isinma_ve_deger():
    assert sma([1.0, 2.0, 3.0, 4.0, 5.0], 3) == [None, None, 2.0, 3.0, 4.0]


def test_ema_ilk_n_degerin_sma_siyla_tohumlanir():
    # k = 2/(3+1) = 0,5; tohum (10+20+30)/3 = 20
    out = ema([10.0, 20.0, 30.0, 25.0, 15.0], 3)
    assert out[:2] == [None, None]
    assert out[2] == pytest.approx(20.0)
    assert out[3] == pytest.approx(25 * 0.5 + 20 * 0.5)        # 22,5
    assert out[4] == pytest.approx(15 * 0.5 + 22.5 * 0.5)      # 18,75


def test_wilder_smooth_tohum_ve_adim():
    out = wilder_smooth([1.0, 2.0, 3.0, 6.0], 3)
    assert out == [None, None, pytest.approx(2.0), pytest.approx((2.0 * 2 + 6.0) / 3)]


def test_gecersiz_periyot_hata_verir():
    with pytest.raises(ValueError):
        sma([1.0, 2.0], 0)
    with pytest.raises(ValueError):
        rsi([1.0, 2.0], -1)
    with pytest.raises(ValueError):
        macd([1.0] * 40, fast=26, slow=12)


# --- RSI ----------------------------------------------------------------------

# StockCharts "Relative Strength Index" çalışma sayfası, tam hassasiyetli
# kapanışlar (iki ondalığa yuvarlanmış kapanışlarla ilk değer 70,46 çıkar).
STOCKCHARTS_CLOSES = [
    44.3389, 44.0902, 44.1497, 43.6124, 44.3278, 44.8264, 45.0955, 45.4245, 45.8433,
    46.0826, 45.8931, 46.0328, 45.6140, 46.2820, 46.2820, 46.0028, 46.0328, 46.4116,
    46.2222, 45.6439, 46.2122, 46.2521, 45.7137, 46.4515, 45.7835, 45.3548, 44.0288,
    44.1783, 44.2181, 44.5672, 43.4205, 42.6628, 43.1314,
]
STOCKCHARTS_RSI = [
    70.53, 66.32, 66.55, 69.41, 66.36, 57.97, 62.93, 63.26, 56.06, 62.38, 54.71,
    50.42, 39.99, 41.46, 41.87, 45.46, 37.30, 33.08, 37.77,
]


def test_rsi_stockcharts_ornegi_iki_ondalikla_tutar():
    out = rsi(STOCKCHARTS_CLOSES, 14)
    assert len(out) == len(STOCKCHARTS_CLOSES)
    assert out[:14] == [None] * 14
    for gozlenen, beklenen in zip(out[14:], STOCKCHARTS_RSI):
        assert gozlenen == pytest.approx(beklenen, abs=0.005)


def test_rsi_duz_seride_50_verir_0_degil():
    # Eski Cutler sürümü burada 0 döndürüyordu; hareket yoksa görüş de yok.
    out = rsi([100.0] * 20, 14)
    assert out[14:] == [50.0] * 6


def test_rsi_tek_yonlu_seride_uclara_gider():
    assert rsi([float(i) for i in range(20)], 14)[-1] == 100.0
    assert rsi([float(20 - i) for i in range(20)], 14)[-1] == pytest.approx(0.0)


# --- ATR ----------------------------------------------------------------------

def test_true_range_ilk_mum_ve_bosluk():
    bars = [Mum(12, 10, 11), Mum(17, 15, 16)]
    # ilk mum: high − low; ikinci mum boşluk açtı: |17 − 11| = 6 > 2
    assert true_range(bars) == [2.0, 6.0]


def test_atr_elle_hesaplanmis_16_mum():
    bars = [
        Mum(12, 10, 11), Mum(13, 11, 12), Mum(15, 12, 14), Mum(14, 13, 13),
        Mum(17, 15, 16), Mum(16, 14, 15), Mum(16, 15, 15), Mum(18, 16, 17),
        Mum(17, 15, 16), Mum(19, 16, 18), Mum(18, 17, 17), Mum(20, 18, 19),
        Mum(19, 17, 18), Mum(21, 19, 20), Mum(20, 17, 19), Mum(24, 20, 22),
    ]
    tr = [2, 2, 3, 1, 4, 2, 1, 3, 2, 3, 1, 3, 2, 3, 3, 5]
    assert true_range(bars) == [float(v) for v in tr]
    tohum = sum(tr[:14]) / 14                     # 32/14
    adim15 = (tohum * 13 + 3) / 14
    adim16 = (adim15 * 13 + 5) / 14
    out = atr(bars, 14)
    assert out[:13] == [None] * 13
    assert out[13] == pytest.approx(tohum)
    assert out[14] == pytest.approx(adim15)
    assert out[15] == pytest.approx(adim16)


def test_atr_duz_seride_sifir():
    assert atr(duz(30), 14)[-1] == 0.0


# --- ADX ----------------------------------------------------------------------

def test_adx_trendde_yukselir_ve_plus_di_ustun():
    bars = disli(20) + yukselen(40)
    adx_line, plus_di, minus_di = adx(bars, 14)
    assert plus_di[-1] > minus_di[-1]
    assert adx_line[-1] > 60.0
    son = [v for v in adx_line[-20:]]
    assert all(a < b for a, b in zip(son, son[1:])), "trend içinde ADX kesintisiz yükselmeli"


def test_adx_testere_disinde_dusuk_kalir():
    adx_line, plus_di, minus_di = adx(disli(60), 14)
    assert adx_line[-1] < 20.0
    assert plus_di[-1] == pytest.approx(minus_di[-1], abs=10.0)


def test_adx_duz_seride_sifir_none_degil():
    # Belgelenmiş karar: yeterli mum varsa ADX 0'dır — "trend yok" ölçülmüş bir sonuçtur.
    adx_line, plus_di, minus_di = adx(duz(40), 14)
    assert adx_line[-1] == 0.0
    assert plus_di[-1] == 0.0 and minus_di[-1] == 0.0


def test_adx_kisa_seride_hizali_none():
    adx_line, plus_di, minus_di = adx(yukselen(5), 14)
    assert adx_line == [None] * 5 and plus_di == [None] * 5 and minus_di == [None] * 5


# --- MACD ---------------------------------------------------------------------

def ema_elle(values, n):
    """Testin kendi bağımsız EMA'sı: SMA tohumu, sonra klasik yineleme."""
    k = 2 / (n + 1)
    out = [None] * len(values)
    cur = sum(values[:n]) / n
    out[n - 1] = cur
    for i in range(n, len(values)):
        cur = values[i] * k + cur * (1 - k)
        out[i] = cur
    return out


def test_macd_elle_hesaplanan_ema_ile_ayni():
    closes = [100 + 10 * math.sin(i / 3) + 0.2 * i for i in range(60)]
    hizli, yavas = ema_elle(closes, 12), ema_elle(closes, 26)
    macd_elle = [None if h is None or y is None else h - y for h, y in zip(hizli, yavas)]
    kuyruk = [v for v in macd_elle if v is not None]
    sinyal_elle = [None] * 25 + ema_elle(kuyruk, 9)
    hist_elle = [None if m is None or s is None else m - s for m, s in zip(macd_elle, sinyal_elle)]

    macd_line, signal_line, histogram = macd(closes, 12, 26, 9)
    assert ilk_gecerli(macd_line) == 25 and ilk_gecerli(signal_line) == 33
    for gozlenen, beklenen in zip((macd_line, signal_line, histogram), (macd_elle, sinyal_elle, hist_elle)):
        for g, b in zip(gozlenen, beklenen):
            assert (g is None and b is None) or g == pytest.approx(b)


# --- stokastik / Williams / CCI -----------------------------------------------

KUCUK_MUMLAR = [Mum(10, 8, 9), Mum(11, 9, 10), Mum(12, 9, 11.5), Mum(12, 10, 10), Mum(13, 11, 12)]


def test_stochastic_elle():
    k_line, d_line = stochastic(KUCUK_MUMLAR, 3, 2)
    assert k_line[:2] == [None, None]
    assert k_line[2] == pytest.approx(100 * (11.5 - 8) / 4)   # 87,5
    assert k_line[3] == pytest.approx(100 * (10 - 9) / 3)     # 33,33
    assert k_line[4] == pytest.approx(100 * (12 - 9) / 4)     # 75
    assert d_line[:3] == [None] * 3
    assert d_line[3] == pytest.approx((87.5 + 100 / 3) / 2)
    assert d_line[4] == pytest.approx((100 / 3 + 75) / 2)


def test_williams_elle():
    out = williams_r(KUCUK_MUMLAR, 3)
    assert out[:2] == [None, None]
    assert out[2] == pytest.approx(-100 * (12 - 11.5) / 4)    # −12,5
    assert out[3] == pytest.approx(-100 * (12 - 10) / 3)      # −66,67
    assert out[4] == pytest.approx(-100 * (13 - 12) / 4)      # −25


def test_cci_elle():
    bars = [Mum(12, 9, 9), Mum(13, 10, 10), Mum(16, 11, 12), Mum(14, 10, 12)]   # TP: 10, 11, 13, 12
    out = cci(bars, 3)
    ort = 34 / 3
    mad = (abs(10 - ort) + abs(11 - ort) + abs(13 - ort)) / 3
    assert out[:2] == [None, None]
    assert out[2] == pytest.approx((13 - ort) / (0.015 * mad))   # tam 100
    assert out[3] == 0.0                                          # TP pencere ortalamasında


def test_roc_yuzde():
    assert roc([100.0, 110.0, 121.0, 133.1], 1)[1:] == pytest.approx([10.0, 10.0, 10.0])
    assert roc([100.0, 110.0, 121.0, 133.1], 2)[2:] == pytest.approx([21.0, 21.0])


def test_duz_seride_osilatorler_notr():
    bars = duz(40)
    k_line, d_line = stochastic(bars, 14, 3)
    assert k_line[-1] == 50.0 and d_line[-1] == 50.0
    assert williams_r(bars, 14)[-1] == -50.0
    assert cci(bars, 20)[-1] == 0.0


def test_cci_duz_seride_yuvarlama_gurultusune_kapilmaz():
    # Ondalık gösterimi tam olmayan bir seviye: pencere ortalaması bir ulp
    # sapabilir; MAD ve sapma aynı büyüklükte olunca oran 66 çıkıyordu.
    assert cci(duz(30, seviye=4471.37), 20)[-1] == 0.0


# --- ısınma, kısa seri, determinizm -------------------------------------------

def test_isinma_uzunluklari_kesin():
    bars = fixture_mumlari()[:80]
    closes = [b.close for b in bars]
    assert ilk_gecerli(sma(closes, 20)) == 19
    assert ilk_gecerli(ema(closes, 20)) == 19
    assert ilk_gecerli(wilder_smooth(closes, 20)) == 19
    assert ilk_gecerli(rsi(closes, 14)) == 14
    assert ilk_gecerli(atr(bars, 14)) == 13
    adx_line, plus_di, minus_di = adx(bars, 14)
    assert ilk_gecerli(plus_di) == 14 and ilk_gecerli(minus_di) == 14
    assert ilk_gecerli(adx_line) == 27          # 2·14 − 1: StockCharts'ta 28. gün
    macd_line, signal_line, histogram = macd(closes, 12, 26, 9)
    assert ilk_gecerli(macd_line) == 25 and ilk_gecerli(signal_line) == 33 and ilk_gecerli(histogram) == 33
    k_line, d_line = stochastic(bars, 14, 3)
    assert ilk_gecerli(k_line) == 13 and ilk_gecerli(d_line) == 15
    assert ilk_gecerli(williams_r(bars, 14)) == 13
    assert ilk_gecerli(cci(bars, 20)) == 19
    assert ilk_gecerli(roc(closes, 12)) == 12
    # Isınmadan sonra boşluk yok
    for seri in (adx_line, signal_line, d_line):
        baslangic = ilk_gecerli(seri)
        assert all(v is not None for v in seri[baslangic:])


def test_kisa_seride_her_yer_none():
    bars = yukselen(3)
    closes = [b.close for b in bars]
    assert rsi(closes) == [None] * 3 and atr(bars) == [None] * 3
    assert all(seri == [None] * 3 for seri in macd(closes))
    assert all(seri == [None] * 3 for seri in stochastic(bars))
    okumalar = latest_indicators(bars)
    assert set(okumalar) == {"rsi", "stochastic", "williams", "cci", "macd", "adx", "atr", "roc"}
    for anahtar, okuma in okumalar.items():
        assert isinstance(okuma, IndicatorReading) and okuma.key == anahtar
        assert okuma.value is None and okuma.state is None
        assert all(v is None for v in okuma.extra.values())
    assert all(row["sma"] is None and row["price_above_sma"] is None for row in moving_average_table(bars))


def test_bos_seri():
    assert rsi([]) == [] and atr([]) == [] and true_range([]) == []
    assert adx([]) == ([], [], []) and macd([]) == ([], [], [])
    assert all(o.value is None for o in latest_indicators([]).values())
    assert moving_averages([], (5, 10)) == {5: (None, None), 10: (None, None)}


def test_deterministik():
    bars = fixture_mumlari()
    assert latest_indicators(bars) == latest_indicators(bars)
    assert adx(bars) == adx(bars)


# --- durum etiketleri ---------------------------------------------------------

def test_durumlar_esikleri_parametreden_okur():
    assert latest_indicators(yukselen(60))["rsi"].state is IndicatorState.OVERBOUGHT
    assert latest_indicators([Mum(200 - i, 199 - i, 199.5 - i) for i in range(60)])["rsi"].state is IndicatorState.OVERSOLD
    assert latest_indicators(duz(60))["rsi"].state is IndicatorState.NEUTRAL
    # Eşik 50'ye çekilince aynı düz seri (RSI 50, ≥ kuralı) aşırı alım olur.
    assert latest_indicators(duz(60), IndicatorParams(rsi_overbought=50.0))["rsi"].state is IndicatorState.OVERBOUGHT


def test_trend_serisinde_tum_durumlar():
    okumalar = latest_indicators(yukselen(60))
    assert okumalar["stochastic"].state is IndicatorState.OVERBOUGHT
    assert okumalar["williams"].state is IndicatorState.OVERBOUGHT
    assert okumalar["cci"].state is IndicatorState.OVERBOUGHT
    assert okumalar["macd"].state is IndicatorState.ABOVE_SIGNAL
    assert okumalar["adx"].state is IndicatorState.TRENDING
    assert okumalar["roc"].state is IndicatorState.POSITIVE
    assert okumalar["adx"].extra["plus_di"] > okumalar["adx"].extra["minus_di"]


def test_macd_durumu_kayan_nokta_gurultusune_kapilmaz():
    # Doğrusal yükselişte MACD ve sinyal aynı değere yakınsar; histogram −1,8e−15
    # kalıyor ve katı işaret kuralı bunu BELOW_SIGNAL okuyordu.
    okuma = latest_indicators(yukselen(60))["macd"]
    assert abs(okuma.extra["histogram"]) < 1e-9
    assert okuma.state is IndicatorState.ABOVE_SIGNAL
    # İvmelenen seri: histogram gerçekten pozitif; yavaşlayan seri: negatif.
    ivmeli = mumlar([100.0 + 0.02 * i * i for i in range(60)])
    assert latest_indicators(ivmeli)["macd"].extra["histogram"] > 1e-3
    assert latest_indicators(ivmeli)["macd"].state is IndicatorState.ABOVE_SIGNAL
    dusen = mumlar([200.0 - 0.02 * i * i for i in range(60)])
    assert latest_indicators(dusen)["macd"].state is IndicatorState.BELOW_SIGNAL
    assert latest_indicators(dusen)["roc"].state is IndicatorState.NEGATIVE


def test_disli_ve_duz_seride_zayif_trend():
    assert latest_indicators(disli(60))["adx"].state is IndicatorState.WEAK_TREND
    assert latest_indicators(duz(60))["adx"].state is IndicatorState.WEAK_TREND


def test_atr_durumu_onceki_medyana_gore():
    # 130 mum sabit 2$ aralık → ATR = 2; sonra 5 geniş mum (6$) ATR'yi 2,6'nın üstüne taşır.
    yuksek = latest_indicators(mumlar([100.0] * 130, aralik=2.0) + mumlar([100.0] * 5, aralik=6.0))["atr"]
    assert yuksek.extra["median"] == pytest.approx(2.0)
    assert yuksek.value / yuksek.extra["median"] >= 1.3
    assert yuksek.state is IndicatorState.HIGH_VOLATILITY

    dusuk = latest_indicators(mumlar([100.0] * 130, aralik=6.0) + duz(12))["atr"]
    assert dusuk.extra["median"] == pytest.approx(6.0)
    assert dusuk.state is IndicatorState.LOW_VOLATILITY

    normal = latest_indicators(mumlar([100.0] * 130, aralik=2.0) + mumlar([100.0], aralik=3.0))["atr"]
    assert normal.state is IndicatorState.NORMAL_VOLATILITY


def test_atr_medyan_penceresi_dolmadan_durum_yok():
    okuma = latest_indicators(duz(50))["atr"]
    assert okuma.value == 0.0
    assert okuma.extra["median"] is None and okuma.state is None


# --- hareketli ortalamalar ----------------------------------------------------

def test_moving_averages_son_degerler():
    closes = [float(i) for i in range(1, 11)]
    out = moving_averages(closes, (3, 20))
    assert out[3][0] == pytest.approx(9.0)
    assert out[3][1] == pytest.approx(ema_elle(closes, 3)[-1])
    assert out[20] == (None, None)


def test_moving_average_table_satirlari():
    bars = yukselen(250)
    tablo = moving_average_table(bars)
    assert [row["period"] for row in tablo] == list(IndicatorParams().ma_periods)
    for row in tablo:
        assert set(row) == {"period", "sma", "ema", "price_above_sma"}
        assert row["price_above_sma"] is True          # yükselen seride fiyat her ortalamanın üstünde
        assert math.isfinite(row["ema"]) and math.isfinite(row["sma"])
    assert tablo[0]["sma"] == pytest.approx(sum(b.close for b in bars[-5:]) / 5)


# --- gerçek veri --------------------------------------------------------------

def test_fixture_uzerinde_deger_araliklari_ve_atr():
    bars = fixture_mumlari()
    assert len(bars) > 300
    okumalar = latest_indicators(bars)
    for okuma in okumalar.values():
        assert okuma.value is not None and math.isfinite(okuma.value), okuma.key
        assert okuma.state is not None, okuma.key
        for ad, v in okuma.extra.items():
            assert v is not None and math.isfinite(v), (okuma.key, ad)
    assert 0.0 <= okumalar["rsi"].value <= 100.0
    assert 0.0 <= okumalar["stochastic"].value <= 100.0
    assert 0.0 <= okumalar["stochastic"].extra["d"] <= 100.0
    assert -100.0 <= okumalar["williams"].value <= 0.0
    assert 0.0 <= okumalar["adx"].value <= 100.0
    assert okumalar["adx"].extra["plus_di"] >= 0.0 and okumalar["adx"].extra["minus_di"] >= 0.0
    assert okumalar["atr"].value > 0.0 and okumalar["atr"].extra["median"] > 0.0
    # Bağımsız hesaplanmış Wilder ATR(14) referansı bu seri için 86,66.
    assert okumalar["atr"].value == pytest.approx(86.66, abs=0.01)
    for row in moving_average_table(bars):
        assert math.isfinite(row["sma"]) and math.isfinite(row["ema"])
