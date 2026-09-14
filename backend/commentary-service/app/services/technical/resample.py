"""Günlük OHLC'den haftalık (cuma etiketli) ve aylık (ay sonu etiketli) mumlar.

Tamamlanma kuralı: bir dönem, `as_of` etiket tarihini geçtiyse tamamlanmıştır. Cuma etiketli
hafta cumartesi girince, ay bir sonraki ayın ilk günü tamamlanır. Devam eden dönem atılır.
"""
from __future__ import annotations

import pandas as pd

_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def _complete_only(bars: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    if len(bars) and bars.index[-1] >= as_of:
        bars = bars.iloc[:-1]
    return bars


def to_weekly(df: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    w = df.resample("W-FRI").agg(_AGG).dropna(subset=["close"])
    return _complete_only(w, as_of)


def to_monthly(df: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    m = df.resample("ME").agg(_AGG).dropna(subset=["close"])
    return _complete_only(m, as_of)
