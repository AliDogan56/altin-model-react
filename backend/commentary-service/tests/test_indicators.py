import numpy as np
import pandas as pd

from app.services.technical.indicators import adx, atr, bollinger_pct_b, macd, rsi


def synthetic_ohlc(n=400, drift=0.0005, seed=7):
    rng = np.random.default_rng(seed)
    close = 2000 * np.exp(np.cumsum(rng.normal(drift, 0.01, n)))
    high = close * (1 + rng.uniform(0.001, 0.01, n))
    low = close * (1 - rng.uniform(0.001, 0.01, n))
    idx = pd.bdate_range("2024-01-01", periods=n)
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": 1000.0}, index=idx)


def test_rsi_bounds_and_direction():
    df = synthetic_ohlc()
    r = rsi(df["close"]).dropna()
    assert ((r >= 0) & (r <= 100)).all()
    up = pd.Series(np.linspace(100, 200, 60))
    assert rsi(up).iloc[-1] > 90


def test_macd_columns_and_atr_positive():
    df = synthetic_ohlc()
    m = macd(df["close"])
    assert set(m.columns) == {"line", "signal", "hist"}
    assert (atr(df).dropna() > 0).all()


def test_adx_and_bollinger_ranges():
    df = synthetic_ohlc()
    a = adx(df).dropna()
    assert ((a["adx"] >= 0) & (a["adx"] <= 100)).all()
    b = bollinger_pct_b(df["close"]).dropna()
    assert b.between(-1, 2).all()
