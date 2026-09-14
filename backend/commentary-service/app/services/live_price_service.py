"""Canlı fiyat: spot izleyen PAXG-USD (7/24), vadeli GC=F gün içi, mümkünse goldprice.org spot.

Günlük hesaplar (momentum, trend, seviye) tamamlanmış mumlara dayanır; bu modül yalnız
"şu an" bloğunu üretir: canlı fiyat, gün içi aralık, önceki kapanışa ve LBMA fiksine göre değişim,
bugünkü hareketin olağan dalgalanmaya (ATR) oranı. Kaynaklar harmanlanmaz, her değer kaynağını taşır.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from ..market_constants import YAHOO_CHART_URL
from .http_client import get_json


def _yahoo_intraday(symbol: str) -> dict:
    data = get_json(YAHOO_CHART_URL.format(symbol=symbol) + "?range=1d&interval=5m")
    res = data["chart"].get("result")
    if not res:
        raise RuntimeError(f"Yahoo {symbol}: {data['chart'].get('error')}")
    r = res[0]
    m = r["meta"]
    closes = [c for c in r["indicators"]["quote"][0]["close"] if c is not None]
    return {
        "kaynak": symbol,
        "fiyat": float(m.get("regularMarketPrice") or closes[-1]),
        "zaman_utc": dt.datetime.fromtimestamp(int(m["regularMarketTime"]), dt.UTC).replace(microsecond=0).isoformat(),
        "onceki_kapanis": float(m["chartPreviousClose"]) if m.get("chartPreviousClose") else None,
        "gun_ici_yuksek": float(m["regularMarketDayHigh"]) if m.get("regularMarketDayHigh") else (max(closes) if closes else None),
        "gun_ici_dusuk": float(m["regularMarketDayLow"]) if m.get("regularMarketDayLow") else (min(closes) if closes else None),
        "mum_sayisi_5dk": len(closes),
    }


def _goldprice_spot() -> dict | None:
    try:
        from curl_cffi import requests as cr  # type: ignore

        r = cr.get("https://data-asg.goldprice.org/dbXRates/USD", impersonate="chrome", timeout=15)
        j = r.json()
        it = j["items"][0]
        return {"kaynak": "goldprice.org", "fiyat": float(it["xauPrice"]), "zaman_utc": dt.datetime.fromtimestamp(int(j["ts"]) / 1000, dt.UTC).replace(microsecond=0).isoformat(), "onceki_kapanis": float(it.get("xauClose") or 0) or None}
    except Exception:  # noqa: BLE001 - isteğe bağlı kaynak
        return None


def live_snapshot(spot_ref_date: pd.Timestamp, spot_ref_price: float, atr_fut: float, basis: float) -> dict:
    now = dt.datetime.now(dt.UTC).replace(microsecond=0)
    out: dict = {"zaman_utc": now.isoformat(), "spot_referans": {"kaynak": "LBMA PM", "tarih": spot_ref_date.strftime("%Y-%m-%d"), "fiyat": round(spot_ref_price, 2)}, "hatalar": {}}
    try:
        out["spot_canli"] = _yahoo_intraday("PAXG-USD")
        out["spot_canli"]["aciklama"] = "Spot izleyen token (PAXG); spot altına yaklaşık ±%0,3 yakın, 7/24 işlem görür."
    except Exception as exc:  # noqa: BLE001
        out["hatalar"]["PAXG-USD"] = str(exc)
    try:
        out["vadeli_canli"] = _yahoo_intraday("GC=F")
        out["vadeli_canli"]["aciklama"] = "COMEX ön ay vadeli; spotun üstünde taşıma maliyeti kadar işlem görür."
    except Exception as exc:  # noqa: BLE001
        out["hatalar"]["GC=F"] = str(exc)
    gp = _goldprice_spot()
    if gp:
        out["spot_goldprice"] = gp
    # canlı spot tercihi: goldprice > PAXG > vadeli × basis
    if gp:
        live, src = gp["fiyat"], "goldprice.org spot"
    elif "spot_canli" in out:
        live, src = out["spot_canli"]["fiyat"], "PAXG-USD (spot izleyen)"
    elif "vadeli_canli" in out:
        live, src = out["vadeli_canli"]["fiyat"] * basis, "GC=F × basis"
    else:
        out["canli_spot"] = None
        return out
    prev = (out.get("spot_canli") or {}).get("onceki_kapanis")
    atr_spot = atr_fut * basis
    out["canli_spot"] = {
        "fiyat": round(live, 2),
        "kaynak": src,
        "fikse_gore_pct": round((live / spot_ref_price - 1) * 100, 2),
        "fikse_gore_dolar": round(live - spot_ref_price, 2),
        "onceki_kapanisa_gore_pct": round((live / prev - 1) * 100, 2) if prev else None,
        "hareket_atr_kati": round((live - spot_ref_price) / atr_spot, 2) if atr_spot else None,
        "atr_spot": round(atr_spot, 2),
    }
    if "spot_canli" in out and "vadeli_canli" in out:
        out["basis_canli"] = round(out["spot_canli"]["fiyat"] / out["vadeli_canli"]["fiyat"], 5)
    return out


def levels_vs_live(levels: dict, live_price: float, margin: float) -> dict:
    ladder = sorted(levels["merdiven"], key=lambda x: x["spot_esdeger"])
    above = [x for x in ladder if x["spot_esdeger"] > live_price + margin][:3]
    below = [x for x in reversed(ladder) if x["spot_esdeger"] < live_price - margin][:3]
    touching = [x for x in ladder if abs(x["spot_esdeger"] - live_price) <= margin]
    close_ref = levels["referans"]["spot_esdeger"]
    crossed = [x for x in ladder if (x["spot_esdeger"] - close_ref) * (x["spot_esdeger"] - live_price) < 0]

    def fmt(x):
        return {**x, "canli_uzaklik_pct": round((x["spot_esdeger"] / live_price - 1) * 100, 2), "canli_uzaklik_dolar": round(x["spot_esdeger"] - live_price, 2)}

    return {"fiyat": round(live_price, 2), "test_marji": round(margin, 2), "direnc": [fmt(x) for x in above], "destek": [fmt(x) for x in below], "test_edilen": [fmt(x) for x in touching], "bugun_gecilen": [fmt(x) for x in crossed]}


def current_price() -> float | None:
    """Tetik kontrolü için tek sayı: PAXG (spot vekili), olmazsa vadeli; ikisi de yoksa None (karar ertelenir)."""
    for symbol in ("PAXG-USD", "GC=F"):
        try:
            return float(_yahoo_intraday(symbol)["fiyat"])
        except Exception:  # noqa: BLE001
            continue
    return None
