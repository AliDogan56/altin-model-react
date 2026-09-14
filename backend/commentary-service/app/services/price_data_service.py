"""Fiyat serileri.

- Spot referans: LBMA PM fiksi (USD/ons), 1968'den günlük, kapanış tek değer.
- OHLCV: COMEX GC=F ön ay vadeli (Yahoo), 2000'den günlük.
- İkisi harmanlanmaz. Vadeli seri teknik hesap için (ATR, pivot, fraktal), spot seri
  getiri ve tahmin defteri için kullanılır. `basis = spot / vadeli kapanış` her gün
  kaydedilir; seviyeler spot eşdeğerine bu oranla çevrilir.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from ..market_constants import (
    LBMA_PM_URL,
    MARKET_CSV,
    PRICES_CSV,
    YAHOO_CHART_URL,
    YAHOO_MARKET_SYMBOLS,
    YAHOO_PERIOD1,
)
from .http_client import get_json


def fetch_lbma_pm() -> pd.DataFrame:
    raw = get_json(LBMA_PM_URL)
    rows = [(r["d"], r["v"][0]) for r in raw if r.get("v") and r["v"][0] is not None]
    df = pd.DataFrame(rows, columns=["date", "spot_close"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    df["spot_close"] = df["spot_close"].astype(float)
    return df


def fetch_yahoo_daily(symbol: str, period1: int = YAHOO_PERIOD1) -> pd.DataFrame:
    period2 = int(dt.datetime.now(dt.UTC).timestamp()) + 86400
    url = YAHOO_CHART_URL.format(symbol=symbol) + f"?period1={period1}&period2={period2}&interval=1d"
    data = get_json(url)
    result = data["chart"].get("result")
    if not result:
        raise RuntimeError(f"Yahoo {symbol}: {data['chart'].get('error')}")
    r = result[0]
    ts = r["timestamp"]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame(
        {
            "date": [dt.datetime.fromtimestamp(t, dt.UTC).date() for t in ts],
            "open": q["open"],
            "high": q["high"],
            "low": q["low"],
            "close": q["close"],
            "volume": q["volume"],
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["close"]).drop_duplicates("date", keep="last").sort_values("date")
    df = df.reset_index(drop=True)
    today = dt.datetime.now(dt.UTC).date()
    df["partial"] = df["date"].dt.date == today
    return df


def build_price_table(spot: pd.DataFrame, fut: pd.DataFrame) -> pd.DataFrame:
    f = fut.rename(
        columns={"open": "fut_open", "high": "fut_high", "low": "fut_low", "close": "fut_close", "volume": "fut_volume"}
    )
    df = pd.merge(spot, f, on="date", how="outer").sort_values("date").reset_index(drop=True)
    both = df["spot_close"].notna() & df["fut_close"].notna() & ~df["partial"].fillna(False).astype(bool)
    df["basis"] = np.where(both, df["spot_close"] / df["fut_close"], np.nan)
    df["basis"] = df["basis"].ffill()
    df["partial"] = df["partial"].fillna(False).astype(bool)
    return df


def update_prices() -> pd.DataFrame:
    spot = fetch_lbma_pm()
    fut = fetch_yahoo_daily("GC=F")
    df = build_price_table(spot, fut)
    PRICES_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PRICES_CSV, index=False)
    return df


def update_market() -> pd.DataFrame:
    frames = []
    errors = {}
    for symbol, name in YAHOO_MARKET_SYMBOLS.items():
        try:
            d = fetch_yahoo_daily(symbol)
            frames.append(d[["date", "close"]].rename(columns={"close": name}))
        except Exception as exc:  # noqa: BLE001 - her sembol bağımsız
            errors[symbol] = str(exc)
    if not frames:
        raise RuntimeError(f"Hiçbir piyasa serisi alınamadı: {errors}")
    df = frames[0]
    for other in frames[1:]:
        df = pd.merge(df, other, on="date", how="outer")
    df = df.sort_values("date").reset_index(drop=True)
    df.attrs["errors"] = errors
    df.to_csv(MARKET_CSV, index=False)
    return df


def load_prices() -> pd.DataFrame:
    df = pd.read_csv(PRICES_CSV, parse_dates=["date"])
    df["partial"] = df["partial"].astype(bool)
    return df


def futures_ohlc(prices: pd.DataFrame, include_partial: bool = False) -> pd.DataFrame:
    """Teknik analiz için tamamlanmış vadeli mumlar; DatetimeIndex, open/high/low/close/volume."""
    df = prices.dropna(subset=["fut_close"]).copy()
    if not include_partial:
        df = df[~df["partial"]]
    out = df[["date", "fut_open", "fut_high", "fut_low", "fut_close", "fut_volume"]].rename(
        columns={"fut_open": "open", "fut_high": "high", "fut_low": "low", "fut_close": "close", "fut_volume": "volume"}
    )
    out = out.set_index("date").astype(float)
    out["volume"] = out["volume"].fillna(0)
    return out


def spot_series(prices: pd.DataFrame) -> pd.Series:
    s = prices.dropna(subset=["spot_close"]).set_index("date")["spot_close"].astype(float)
    return s
