"""Üç çerçevede momentum skoru.

Sabit eşik yok: her gösterge kendi son N barlık standart sapmasına bölünür ve ±2σ'da doyurulur
([-1, +1]). Editoryal ağırlıklarla toplanır, ×100 ölçeklenir. İşaret göstergenin kendi işaretidir
(RSI-50, MACD histogramı, getiri, ortalamaya göre konum...), büyüklük tarihsel dağılıma göredir.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ...market_constants import MOMENTUM_WINDOWS
from .indicators import adx, bollinger_pct_b, ema, macd, roc, rsi, sma

EPS = 1e-12


def scale_score(series: pd.Series, window: int) -> tuple[float, float]:
    s = series.dropna()
    if len(s) < 20:
        return float("nan"), float("nan")
    tail = s.iloc[-window:]
    sd = float(tail.std(ddof=0))
    v = float(s.iloc[-1])
    if sd < EPS:
        return v, 0.0
    return v, float(np.clip(v / (2 * sd), -1.0, 1.0))


def daily_components(df: pd.DataFrame) -> dict[str, tuple[pd.Series, float]]:
    c = df["close"]
    m = macd(c)
    a = adx(df)
    hist_n = m["hist"] / c
    e20, e50 = ema(c, 20), ema(c, 50)
    signed_adx = a["adx"] / 100 * np.sign(a["plus_di"] - a["minus_di"])
    return {
        "rsi14_merkezli": (rsi(c) - 50, 0.15),
        "macd_hist": (hist_n, 0.15),
        "macd_hist_egim3": (hist_n.diff(3), 0.10),
        "roc10": (roc(c, 10), 0.15),
        "ema20_konum": (c / e20 - 1, 0.10),
        "ema50_konum": (c / e50 - 1, 0.10),
        "ema20_egim5": (e20.pct_change(5), 0.10),
        "adx14_yonlu": (signed_adx, 0.10),
        "bollinger_pctb_merkezli": (bollinger_pct_b(c) - 0.5, 0.05),
    }


def weekly_components(df: pd.DataFrame) -> dict[str, tuple[pd.Series, float]]:
    c = df["close"]
    m = macd(c)
    a = adx(df)
    signed_adx = a["adx"] / 100 * np.sign(a["plus_di"] - a["minus_di"])
    return {
        "rsi14_merkezli": (rsi(c) - 50, 0.20),
        "macd_hist": (m["hist"] / c, 0.20),
        "roc13": (roc(c, 13), 0.20),
        "sma10_konum": (c / sma(c, 10) - 1, 0.15),
        "sma40_konum": (c / sma(c, 40) - 1, 0.15),
        "adx14_yonlu": (signed_adx, 0.10),
    }


def monthly_components(df: pd.DataFrame) -> dict[str, tuple[pd.Series, float]]:
    c = df["close"]
    m = macd(c)
    return {
        "getiri_12_1": (c.shift(1) / c.shift(12) - 1, 0.30),
        "roc3": (roc(c, 3), 0.15),
        "roc6": (roc(c, 6), 0.15),
        "sma10_konum": (c / sma(c, 10) - 1, 0.15),
        "macd_hist": (m["hist"] / c, 0.15),
        "rsi14_merkezli": (rsi(c) - 50, 0.10),
    }


def label(score: float) -> str:
    if np.isnan(score):
        return "veri yetersiz"
    if score > 60:
        return "güçlü yükseliş"
    if score > 20:
        return "yükseliş"
    if score >= -20:
        return "nötr"
    if score > -60:
        return "düşüş"
    return "güçlü düşüş"


def frame_score(components: dict[str, tuple[pd.Series, float]], window: int, bars: int) -> dict:
    parts, total, wsum = {}, 0.0, 0.0
    for name, (series, weight) in components.items():
        value, sc = scale_score(series, window)
        parts[name] = {"deger": None if np.isnan(value) else round(value, 6), "skor": None if np.isnan(sc) else round(sc, 3), "agirlik": weight}
        if not np.isnan(sc):
            total += weight * sc
            wsum += weight
    score = float("nan") if wsum == 0 else 100 * total / wsum  # eksik bileşenin ağırlığı kalanlara dağılır
    return {"skor": None if np.isnan(score) else round(score, 1), "etiket": label(score), "pencere": window, "bar_sayisi": bars, "bilesenler": parts}


def _sign(score: float | None) -> int:
    if score is None:
        return 0
    return 1 if score > 20 else (-1 if score < -20 else 0)


def alignment(d: float | None, w: float | None, m: float | None) -> dict:
    sd, sw, sm = _sign(d), _sign(w), _sign(m)
    if sd == sw == sm == 1:
        state, desc = "hizali_yukselis", "Üç çerçeve de yükseliş yönünde; trend ve kısa vade aynı tarafta."
    elif sd == sw == sm == -1:
        state, desc = "hizali_dusus", "Üç çerçeve de düşüş yönünde."
    elif sm == 1 and sd == -1:
        state, desc = "yukselis_icinde_duzeltme", "Aylık çerçeve yükseliş, günlük çerçeve düşüş: trend içinde düzeltme."
    elif sm == -1 and sd == 1:
        state, desc = "dusus_icinde_tepki", "Aylık çerçeve düşüş, günlük çerçeve yükseliş: düşüş içinde tepki."
    else:
        state, desc = "karisik", "Çerçeveler hemfikir değil ya da nötr; yön iddiası zayıf."
    return {"durum": state, "aciklama": desc, "isaretler": {"gunluk": sd, "haftalik": sw, "aylik": sm}}


def compute_momentum(daily: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame, as_of: pd.Timestamp) -> dict:
    d = frame_score(daily_components(daily), MOMENTUM_WINDOWS["daily"], len(daily))
    w = frame_score(weekly_components(weekly), MOMENTUM_WINDOWS["weekly"], len(weekly))
    m = frame_score(monthly_components(monthly), MOMENTUM_WINDOWS["monthly"], len(monthly))
    return {
        "as_of": as_of.strftime("%Y-%m-%d"),
        "son_bar": {"gunluk": daily.index[-1].strftime("%Y-%m-%d"), "haftalik": weekly.index[-1].strftime("%Y-%m-%d"), "aylik": monthly.index[-1].strftime("%Y-%m-%d")},
        "yontem": "Gösterge / (2 × son N bar standart sapması), ±1'de doyurulur; ağırlıklı toplam × 100.",
        "cerceveler": {"gunluk": d, "haftalik": w, "aylik": m},
        "hizalanma": alignment(d["skor"], w["skor"], m["skor"]),
    }
