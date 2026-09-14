"""FRED gözlemleri. Her satır obs_date, value, available_at (obs_date + yaklaşık yayın gecikmesi) taşır.

Gerçek yayın tarihi (vintage) için ALFRED gerekir; bu dosya onu yapmaz ve yaptığını iddia etmez.
"""
from __future__ import annotations

import datetime as dt
import io

import pandas as pd

from ..market_constants import FRED_CSV_URL, FRED_SERIES, MACRO_CSV, TREASURY_CSV_URL
from .http_client import get_text


def fetch_fred_series(series_id: str) -> pd.DataFrame:
    text = get_text(FRED_CSV_URL.format(series=series_id), impersonate=True)
    df = pd.read_csv(io.StringIO(text))
    df.columns = ["obs_date", "value"]
    df["obs_date"] = pd.to_datetime(df["obs_date"])
    df["value"] = pd.to_numeric(df["value"].replace(".", pd.NA), errors="coerce")
    df = df.dropna(subset=["value"]).reset_index(drop=True)
    return df


def fetch_treasury_10y(year: int, real: bool) -> pd.DataFrame:
    kind = "daily_treasury_real_yield_curve" if real else "daily_treasury_yield_curve"
    text = get_text(TREASURY_CSV_URL.format(year=year, kind=kind))
    df = pd.read_csv(io.StringIO(text))
    col = "10 YR" if real else "10 Yr"
    out = pd.DataFrame({"obs_date": pd.to_datetime(df["Date"]), "value": pd.to_numeric(df[col], errors="coerce")})
    return out.dropna().sort_values("obs_date").reset_index(drop=True)


def update_macro_store() -> tuple[pd.DataFrame, dict]:
    fetched_at = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    frames, errors = [], {}
    for series_id, meta in FRED_SERIES.items():
        try:
            d = fetch_fred_series(series_id)
            source = "FRED"
        except Exception as exc:  # noqa: BLE001
            errors[series_id] = str(exc)
            if series_id in ("DFII10", "DGS10"):
                try:
                    year = dt.date.today().year
                    d = pd.concat([fetch_treasury_10y(year - 1, series_id == "DFII10"), fetch_treasury_10y(year, series_id == "DFII10")])
                    source = "Treasury"
                except Exception as exc2:  # noqa: BLE001
                    errors[series_id] += f" | Treasury yedek: {exc2}"
                    continue
            else:
                continue
        d = d.copy()
        d["series"] = series_id
        d["available_at"] = d["obs_date"] + pd.Timedelta(days=meta["lag_days"])
        d["source"] = source
        d["fetched_at"] = fetched_at
        frames.append(d)
    if not frames:
        raise RuntimeError(f"Hiçbir makro seri alınamadı: {errors}")
    df = pd.concat(frames, ignore_index=True)[["series", "obs_date", "value", "available_at", "source", "fetched_at"]]
    MACRO_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(MACRO_CSV, index=False)
    return df, errors


def load_macro() -> pd.DataFrame:
    return pd.read_csv(MACRO_CSV, parse_dates=["obs_date", "available_at"])


def known_as_of(df: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """PIT kuralı: yalnız available_at <= as_of olan gözlemler."""
    return df[df["available_at"] <= as_of]


def latest_values(df: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    k = known_as_of(df, as_of).sort_values("obs_date")
    last = k.groupby("series").tail(1).set_index("series")
    out = last[["obs_date", "value", "available_at", "source"]].copy()
    out["desc"] = [FRED_SERIES.get(s, {}).get("desc", "") for s in out.index]
    return out
