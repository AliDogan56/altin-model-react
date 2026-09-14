"""Destek ve direnç merdiveni. Sekiz kaynaktan aday seviye, ATR toleransıyla kümeleme, puan.

Puan = Σ (kaynak ağırlığı × zaman yakınlığı). Fiyatın "test ediliyor" marjı içindeki seviye hedef
olarak gösterilmez, `test_edilen` alanında ayrı döner. Seviyeler vadeli seride hesaplanır ve
`basis` (spot/vadeli) ile spot eşdeğerine çevrilir.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ...market_constants import LEVEL_TOL_ATR, TOUCH_MARGIN_ATR
from .indicators import sma
from .trendlines import fractal_swings

SOURCE_WEIGHTS = {
    "haftalik_pivot": 0.8,
    "aylik_pivot": 1.0,
    "fib": 0.6,
    "fib_ana": 0.8,      # 0,5 ve 0,618
    "sma50": 0.7,
    "sma100": 0.6,
    "sma200": 1.0,
    "sma10h": 0.6,
    "sma40h": 0.9,
    "yuvarlak_100": 0.5,
    "yuvarlak_50": 0.25,
    "tum_zamanlarin_zirvesi": 1.0,
}


def swing_levels(daily: pd.DataFrame, tol: float, lookback: int = 250, wing: int = 3, half_life: int = 126) -> list[dict]:
    window = daily.iloc[-lookback:]
    sw = fractal_swings(window, wing)
    if sw.empty:
        return []
    last_idx = len(window) - 1
    sw = sw.sort_values("price").reset_index(drop=True)
    clusters: list[list[int]] = []
    for i in range(len(sw)):
        if clusters and sw.loc[i, "price"] - np.mean([sw.loc[j, "price"] for j in clusters[-1]]) <= tol:
            clusters[-1].append(i)
        else:
            clusters.append([i])
    out = []
    for cl in clusters:
        members = sw.loc[cl]
        age = last_idx - int(members["idx"].max())
        recency = math.exp(-math.log(2) * age / half_life)
        out.append(
            {
                "fiyat": float(members["price"].mean()),
                "kaynak": "salinim",
                "agirlik": float(len(members)),
                "yakinlik": recency,
                "temas": int(len(members)),
                "son_temas": window.index[int(members["idx"].max())].strftime("%Y-%m-%d"),
            }
        )
    return out


def pivot_levels(bar: pd.Series, prefix: str) -> list[dict]:
    h, l, c = float(bar["high"]), float(bar["low"]), float(bar["close"])
    p = (h + l + c) / 3
    rng = h - l
    levels = {"P": p, "R1": 2 * p - l, "S1": 2 * p - h, "R2": p + rng, "S2": p - rng, "R3": h + 2 * (p - l), "S3": l - 2 * (h - p)}
    w = SOURCE_WEIGHTS[f"{prefix}_pivot"]
    return [{"fiyat": v, "kaynak": f"{prefix}_pivot_{k}", "agirlik": w, "yakinlik": 1.0} for k, v in levels.items()]


def fibonacci_levels(daily: pd.DataFrame, lookback: int = 250) -> tuple[list[dict], dict]:
    w = daily.iloc[-lookback:]
    hi_i, lo_i = int(w["high"].to_numpy().argmax()), int(w["low"].to_numpy().argmin())
    hi, lo = float(w["high"].iloc[hi_i]), float(w["low"].iloc[lo_i])
    rng = hi - lo
    out = []
    if lo_i < hi_i:  # yükseliş salınımı: düzeltmeler zirveden aşağı
        yon = "yukselis"
        for r in (0.236, 0.382, 0.5, 0.618, 0.786):
            out.append({"fiyat": hi - r * rng, "kaynak": f"fib_{r}", "agirlik": SOURCE_WEIGHTS["fib_ana" if r in (0.5, 0.618) else "fib"], "yakinlik": 1.0})
        for e in (1.272, 1.618):
            out.append({"fiyat": hi + (e - 1) * rng, "kaynak": f"fib_uzanti_{e}", "agirlik": SOURCE_WEIGHTS["fib"], "yakinlik": 1.0})
    else:
        yon = "dusus"
        for r in (0.236, 0.382, 0.5, 0.618, 0.786):
            out.append({"fiyat": lo + r * rng, "kaynak": f"fib_{r}", "agirlik": SOURCE_WEIGHTS["fib_ana" if r in (0.5, 0.618) else "fib"], "yakinlik": 1.0})
        for e in (1.272, 1.618):
            out.append({"fiyat": lo - (e - 1) * rng, "kaynak": f"fib_uzanti_{e}", "agirlik": SOURCE_WEIGHTS["fib"], "yakinlik": 1.0})
    meta = {"yon": yon, "dip": {"tarih": w.index[lo_i].strftime("%Y-%m-%d"), "fiyat": round(lo, 2)}, "tepe": {"tarih": w.index[hi_i].strftime("%Y-%m-%d"), "fiyat": round(hi, 2)}}
    return out, meta


def ma_levels(daily: pd.DataFrame, weekly: pd.DataFrame) -> list[dict]:
    out = []
    for n, key in ((50, "sma50"), (100, "sma100"), (200, "sma200")):
        v = sma(daily["close"], n).iloc[-1]
        if not np.isnan(v):
            out.append({"fiyat": float(v), "kaynak": key, "agirlik": SOURCE_WEIGHTS[key], "yakinlik": 1.0})
    for n, key in ((10, "sma10h"), (40, "sma40h")):
        v = sma(weekly["close"], n).iloc[-1]
        if not np.isnan(v):
            out.append({"fiyat": float(v), "kaynak": key, "agirlik": SOURCE_WEIGHTS[key], "yakinlik": 1.0})
    return out


def round_levels(price: float, pct: float = 0.06) -> list[dict]:
    lo, hi = price * (1 - pct), price * (1 + pct)
    out = []
    v = math.floor(lo / 50) * 50
    while v <= hi:
        if v >= lo:
            key = "yuvarlak_100" if v % 100 == 0 else "yuvarlak_50"
            out.append({"fiyat": float(v), "kaynak": key, "agirlik": SOURCE_WEIGHTS[key], "yakinlik": 1.0})
        v += 50
    return out


def merge_levels(cands: list[dict], tol: float) -> list[dict]:
    cands = sorted(cands, key=lambda d: d["fiyat"])
    groups: list[list[dict]] = []
    for c in cands:
        if groups and c["fiyat"] - np.mean([g["fiyat"] for g in groups[-1]]) <= tol:
            groups[-1].append(c)
        else:
            groups.append([c])
    merged = []
    for g in groups:
        wsum = sum(m["agirlik"] * m["yakinlik"] for m in g)
        price = sum(m["fiyat"] * m["agirlik"] * m["yakinlik"] for m in g) / wsum if wsum else float(np.mean([m["fiyat"] for m in g]))
        merged.append(
            {
                "fiyat": price,
                "puan": round(wsum, 3),
                "kaynaklar": [m["kaynak"] for m in g],
                "kaynak_sayisi": len(g),
                "temas": sum(m.get("temas", 0) for m in g),
            }
        )
    return merged


def compute_levels(daily: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame, atr_last: float, basis: float, as_of: pd.Timestamp) -> dict:
    price = float(daily["close"].iloc[-1])
    tol = atr_last * LEVEL_TOL_ATR
    margin = atr_last * TOUCH_MARGIN_ATR
    cands = swing_levels(daily, tol)
    cands += pivot_levels(weekly.iloc[-1], "haftalik")
    cands += pivot_levels(monthly.iloc[-1], "aylik")
    fib, fib_meta = fibonacci_levels(daily)
    cands += fib
    cands += ma_levels(daily, weekly)
    cands += round_levels(price)
    ath = float(daily["high"].max())
    cands.append({"fiyat": ath, "kaynak": "tum_zamanlarin_zirvesi", "agirlik": SOURCE_WEIGHTS["tum_zamanlarin_zirvesi"], "yakinlik": 1.0})
    ladder = merge_levels(cands, tol)

    def fmt(lv: dict) -> dict:
        return {
            "vadeli": round(lv["fiyat"], 2),
            "spot_esdeger": round(lv["fiyat"] * basis, 2),
            "uzaklik_pct": round((lv["fiyat"] / price - 1) * 100, 2),
            "puan": lv["puan"],
            "kaynak_sayisi": lv["kaynak_sayisi"],
            "kaynaklar": lv["kaynaklar"],
            "temas": lv["temas"],
        }

    touching = [fmt(lv) for lv in ladder if abs(lv["fiyat"] - price) <= margin]
    above = [fmt(lv) for lv in ladder if lv["fiyat"] > price + margin][:3]
    below = [fmt(lv) for lv in reversed(ladder) if lv["fiyat"] < price - margin][:3]
    return {
        "as_of": as_of.strftime("%Y-%m-%d"),
        "son_bar": daily.index[-1].strftime("%Y-%m-%d"),
        "referans": {"vadeli_kapanis": round(price, 2), "spot_esdeger": round(price * basis, 2), "basis": round(basis, 5), "atr14": round(atr_last, 2), "tolerans": round(tol, 2), "test_marji": round(margin, 2)},
        "not": "Seviyeler GC=F vadeli seride hesaplanır; spot_esdeger = vadeli × basis (LBMA PM / vadeli kapanış, 20 günlük medyan). Günlük hesap son tamamlanan kapanışa aittir; canlı fiyata göre konum `canli` bloğundadır.",
        "direnc": above,
        "destek": below,
        "test_edilen": touching,
        "fibonacci_salinimi": fib_meta,
        "merdiven": [fmt(lv) for lv in ladder if abs(lv["fiyat"] / price - 1) <= 0.12],
    }
