"""Salınım noktaları, trend çizgileri, log-regresyon kanalı ve trend durumu."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ...market_constants import CHANNEL_WINDOWS, SWING_WING_DAILY
from .indicators import adx, sma


def fractal_swings(df: pd.DataFrame, wing: int) -> pd.DataFrame:
    highs, lows = df["high"].to_numpy(), df["low"].to_numpy()
    rows = []
    for i in range(wing, len(df) - wing):
        left_h, right_h = highs[i - wing:i], highs[i + 1:i + wing + 1]
        left_l, right_l = lows[i - wing:i], lows[i + 1:i + wing + 1]
        if highs[i] > left_h.max() and highs[i] >= right_h.max():
            rows.append((i, df.index[i], float(highs[i]), "tepe"))
        if lows[i] < left_l.min() and lows[i] <= right_l.min():
            rows.append((i, df.index[i], float(lows[i]), "dip"))
    return pd.DataFrame(rows, columns=["idx", "date", "price", "kind"])


def _line(x1: float, y1: float, x2: float, y2: float):
    slope = (y2 - y1) / (x2 - x1)
    return slope, y1 - slope * x1


def best_trend_line(swings: pd.DataFrame, kind: str, closes: pd.Series, tol: float, max_points: int = 5) -> dict | None:
    pts = swings[swings["kind"] == kind].tail(max_points).reset_index(drop=True)
    if len(pts) < 2:
        return None
    n_last = len(closes) - 1
    c = closes.to_numpy()
    best = None
    for a in range(len(pts)):
        for b in range(a + 1, len(pts)):
            xa, ya, xb, yb = pts.loc[a, "idx"], pts.loc[a, "price"], pts.loc[b, "idx"], pts.loc[b, "price"]
            slope, intercept = _line(xa, ya, xb, yb)
            line_at = lambda x: slope * x + intercept  # noqa: E731
            touches = int(sum(abs(p - line_at(x)) <= tol for x, p in zip(pts["idx"], pts["price"]) if x >= xa))
            seg = np.arange(int(xa), n_last + 1)
            if kind == "dip":
                broken = bool(np.any(c[seg] < line_at(seg) - tol))
            else:
                broken = bool(np.any(c[seg] > line_at(seg) + tol))
            key = (not broken, touches, xb)
            if best is None or key > best["key"]:
                value_today = float(line_at(n_last))
                best = {
                    "key": key,
                    "tur": "destek_cizgisi" if kind == "dip" else "direnc_cizgisi",
                    "noktalar": [
                        {"tarih": pts.loc[a, "date"].strftime("%Y-%m-%d"), "fiyat": round(float(ya), 2)},
                        {"tarih": pts.loc[b, "date"].strftime("%Y-%m-%d"), "fiyat": round(float(yb), 2)},
                    ],
                    "temas": touches,
                    "kirildi": broken,
                    "egim_bar_basina": round(float(slope), 4),
                    "egim_gunluk_pct": round(float(slope / value_today * 100), 4) if value_today else None,
                    "bugunku_deger": round(value_today, 2),
                    "5_bar_sonra": round(float(line_at(n_last + 5)), 2),
                    "fiyatin_uzakligi_pct": round(float((c[-1] / value_today - 1) * 100), 3) if value_today else None,
                }
    if best:
        best.pop("key")
    return best


def _spot(v, basis):
    return None if v is None else round(float(v) * basis, 2)


def regression_channel(close: pd.Series, window: int) -> dict | None:
    if len(close) < window:
        return None
    y = np.log(close.to_numpy()[-window:])
    x = np.arange(window, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fit = slope * x + intercept
    resid = y - fit
    sigma = float(resid.std(ddof=0))
    syy = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 if syy < 1e-10 else float(1 - (resid**2).sum() / syy)
    last_fit = float(fit[-1])
    pos = 0.0 if sigma < 1e-12 else float(resid[-1] / sigma)
    return {
        "pencere": window,
        "egim_gunluk_pct": round(float((np.exp(slope) - 1) * 100), 4),
        "egim_yillik_pct": round(float((np.exp(slope * 252) - 1) * 100), 2),
        "r2": round(r2, 3),
        "sigma_pct": round(sigma * 100, 3),
        "konum_sigma": round(pos, 2),
        "orta": round(float(np.exp(last_fit)), 2),
        "ust_1s": round(float(np.exp(last_fit + sigma)), 2),
        "alt_1s": round(float(np.exp(last_fit - sigma)), 2),
        "ust_2s": round(float(np.exp(last_fit + 2 * sigma)), 2),
        "alt_2s": round(float(np.exp(last_fit - 2 * sigma)), 2),
    }


def dow_state(swings: pd.DataFrame) -> dict:
    highs = swings[swings["kind"] == "tepe"].tail(2)["price"].tolist()
    lows = swings[swings["kind"] == "dip"].tail(2)["price"].tolist()
    if len(highs) < 2 or len(lows) < 2:
        return {"durum": "belirsiz", "aciklama": "Yeterli salınım yok."}
    hh, hl = highs[1] > highs[0], lows[1] > lows[0]
    lh, ll = highs[1] < highs[0], lows[1] < lows[0]
    if hh and hl:
        return {"durum": "yukselis", "aciklama": "Yüksek tepe ve yüksek dip."}
    if lh and ll:
        return {"durum": "dusus", "aciklama": "Alçak tepe ve alçak dip."}
    return {"durum": "yatay", "aciklama": "Tepe ve dipler aynı yönde değil."}


def compute_trend(daily: pd.DataFrame, atr_last: float, as_of: pd.Timestamp, wing: int = SWING_WING_DAILY, basis: float = 1.0) -> dict:
    swings = fractal_swings(daily, wing)
    tol = atr_last * 0.5
    c = daily["close"]
    support = best_trend_line(swings, "dip", c, tol)
    resistance = best_trend_line(swings, "tepe", c, tol)
    channels = {str(w): regression_channel(c, w) for w in CHANNEL_WINDOWS}
    s50, s200 = sma(c, 50), sma(c, 200)
    a = adx(daily)
    last_low = swings[swings["kind"] == "dip"].tail(1)
    last_high = swings[swings["kind"] == "tepe"].tail(1)
    price = float(c.iloc[-1])
    ma_state = {
        "fiyat_sma50_pct": round((price / float(s50.iloc[-1]) - 1) * 100, 2) if not np.isnan(s50.iloc[-1]) else None,
        "fiyat_sma200_pct": round((price / float(s200.iloc[-1]) - 1) * 100, 2) if not np.isnan(s200.iloc[-1]) else None,
        "sma50_ustunde_sma200": bool(s50.iloc[-1] > s200.iloc[-1]) if not (np.isnan(s50.iloc[-1]) or np.isnan(s200.iloc[-1])) else None,
        "sma50": round(float(s50.iloc[-1]), 2) if not np.isnan(s50.iloc[-1]) else None,
        "sma200": round(float(s200.iloc[-1]), 2) if not np.isnan(s200.iloc[-1]) else None,
    }
    for ln in (support, resistance):
        if ln:
            ln["bugunku_deger_spot"] = _spot(ln["bugunku_deger"], basis)
            ln["5_bar_sonra_spot"] = _spot(ln["5_bar_sonra"], basis)
    ma_state["sma50_spot"], ma_state["sma200_spot"] = _spot(ma_state["sma50"], basis), _spot(ma_state["sma200"], basis)
    return {
        "as_of": as_of.strftime("%Y-%m-%d"),
        "son_bar": daily.index[-1].strftime("%Y-%m-%d"),
        "fiyat": round(price, 2),
        "fiyat_spot_esdeger": _spot(price, basis),
        "basis": round(basis, 5),
        "not": "Vadeli seride hesaplanır; *_spot alanları = vadeli × basis.",
        "atr14": round(atr_last, 2),
        "tolerans": round(tol, 2),
        "dow": dow_state(swings),
        "ortalamalar": ma_state,
        "adx14": round(float(a["adx"].iloc[-1]), 1),
        "trend_cizgileri": {"destek": support, "direnc": resistance},
        "regresyon_kanali": channels,
        "gecersizleme": {
            "son_dip": {"tarih": last_low["date"].iloc[0].strftime("%Y-%m-%d"), "fiyat": round(float(last_low["price"].iloc[0]), 2), "fiyat_spot": _spot(last_low["price"].iloc[0], basis)} if len(last_low) else None,
            "son_tepe": {"tarih": last_high["date"].iloc[0].strftime("%Y-%m-%d"), "fiyat": round(float(last_high["price"].iloc[0]), 2), "fiyat_spot": _spot(last_high["price"].iloc[0], basis)} if len(last_high) else None,
        },
        "son_salinimlar": [
            {"tarih": r.date.strftime("%Y-%m-%d"), "fiyat": round(r.price, 2), "fiyat_spot": _spot(r.price, basis), "tur": r.kind} for r in swings.tail(8).itertuples()
        ],
    }
