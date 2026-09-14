"""Taban koni: sıfır sürüklenme, gerçekleşen oynaklık, lognormal yaklaşım.

Bu bir tahmin değildir; masanın "görüş yok" durumundaki dürüst sıfır noktasıdır. Model
bileşenleri (GARCH, makro regresyon, TSMOM, senaryolar) Faz 2'de bu koniyi kaydırır.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

Z10, Z90 = -1.2815515655446004, 1.2815515655446004
HORIZONS = {"1_ay": 21, "3_ay": 63, "6_ay": 126}


def realized_vol(spot: pd.Series, window: int) -> float:
    r = np.log(spot).diff().dropna().iloc[-window:]
    return float(r.std(ddof=0))


def base_cone(spot: pd.Series, as_of: pd.Timestamp, window: int = 63) -> dict:
    s0 = float(spot.iloc[-1])
    sd = realized_vol(spot, window)
    sd_252 = realized_vol(spot, 252)
    out = {
        "as_of": as_of.strftime("%Y-%m-%d"),
        "spot_tarih": spot.index[-1].strftime("%Y-%m-%d"),
        "spot": round(s0, 2),
        "yontem": f"Sıfır sürüklenme; günlük log getiri σ son {window} gün (ddof=0); lognormal; P10/P90 = ±1,2816σ√h.",
        "sigma_gunluk_pct": round(sd * 100, 3),
        "sigma_yillik_pct_63g": round(sd * math.sqrt(252) * 100, 2),
        "sigma_yillik_pct_252g": round(sd_252 * math.sqrt(252) * 100, 2),
        "gorus": "yok",
        "ufuklar": {},
    }
    for name, h in HORIZONS.items():
        sh = sd * math.sqrt(h)
        out["ufuklar"][name] = {
            "islem_gunu": h,
            "sigma_pct": round(sh * 100, 2),
            "p10": round(s0 * math.exp(Z10 * sh), 2),
            "p50": round(s0, 2),
            "p90": round(s0 * math.exp(Z90 * sh), 2),
            "bant_80_pct": round((math.exp(Z90 * sh) - 1) * 100, 2),
        }
    return out
