"""Tahmin defteri: yalnız ekleme. Tahmin `forecasts.csv`'ye, çözümleme `outcomes.csv`'ye yazılır.

Bir kayıt asla değiştirilmez; düzeltme yeni kayıttır. Puanlama betikte yapılır, ajan yorumlar.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json

import pandas as pd

from ..market_constants import LEDGER_DIR

FORECASTS = LEDGER_DIR / "forecasts.csv"
OUTCOMES = LEDGER_DIR / "outcomes.csv"

FORECAST_FIELDS = [
    "forecast_id", "issued_at", "as_of_date", "base_price", "price_source", "horizon_days", "target_date",
    "p10", "p50", "p90", "p_up", "p_bull", "p_base", "p_bear", "method_version", "inputs_hash", "note",
]
OUTCOME_FIELDS = ["forecast_id", "actual_date", "actual_price", "actual_return", "pinball", "in_80", "direction_hit", "resolved_at"]


def _append(path, fields, row: dict) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})


def add_forecast(rec: dict) -> str:
    as_of = pd.Timestamp(rec["as_of_date"])
    target = as_of + pd.Timedelta(days=int(rec["horizon_days"]))
    digest = hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest()[:8]
    fid = f"{as_of:%Y%m%d}-{int(rec['horizon_days'])}g-{digest}"
    row = dict(rec)
    row.update(
        forecast_id=fid,
        issued_at=rec.get("issued_at") or dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        target_date=target.strftime("%Y-%m-%d"),
    )
    _append(FORECASTS, FORECAST_FIELDS, row)
    return fid


def load_forecasts() -> pd.DataFrame:
    if not FORECASTS.exists():
        return pd.DataFrame(columns=FORECAST_FIELDS)
    return pd.read_csv(FORECASTS, parse_dates=["as_of_date", "target_date"])


def load_outcomes() -> pd.DataFrame:
    if not OUTCOMES.exists():
        return pd.DataFrame(columns=OUTCOME_FIELDS)
    return pd.read_csv(OUTCOMES, parse_dates=["actual_date"])


def pinball(q: float, pred: float, actual: float) -> float:
    d = actual - pred
    return max(q * d, (q - 1) * d)


def resolve(spot: pd.Series, today: pd.Timestamp, grace_days: int = 7) -> list[dict]:
    """Vadesi dolan tahminleri hedef tarihten sonraki ilk spot kapanışla puanlar."""
    fc, done = load_forecasts(), load_outcomes()
    resolved_ids = set(done["forecast_id"]) if len(done) else set()
    new = []
    spot = spot.sort_index()
    for r in fc.itertuples():
        if r.forecast_id in resolved_ids or r.target_date > today:
            continue
        window = spot[(spot.index >= r.target_date) & (spot.index <= r.target_date + pd.Timedelta(days=grace_days))]
        if window.empty:
            continue
        actual_date, actual = window.index[0], float(window.iloc[0])
        base = float(r.base_price)
        pb = (pinball(0.1, float(r.p10), actual) + pinball(0.5, float(r.p50), actual) + pinball(0.9, float(r.p90), actual)) / 3
        p_up = float(r.p_up) if pd.notna(r.p_up) else None
        row = {
            "forecast_id": r.forecast_id,
            "actual_date": actual_date.strftime("%Y-%m-%d"),
            "actual_price": round(actual, 2),
            "actual_return": round(actual / base - 1, 6),
            "pinball": round(pb, 4),
            "in_80": bool(float(r.p10) <= actual <= float(r.p90)),
            "direction_hit": None if p_up is None else bool((actual > base) == (p_up > 0.5)),
            "resolved_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        }
        _append(OUTCOMES, OUTCOME_FIELDS, row)
        new.append(row)
    return new


def summary() -> dict:
    fc, oc = load_forecasts(), load_outcomes()
    out = {"tahmin_sayisi": int(len(fc)), "cozumlenen": int(len(oc)), "bekleyen": int(len(fc) - len(oc))}
    if len(oc):
        merged = oc.merge(fc[["forecast_id", "horizon_days"]], on="forecast_id", how="left")
        by_h = {}
        for h, g in merged.groupby("horizon_days"):
            dir_vals = g["direction_hit"].dropna()
            by_h[str(int(h))] = {
                "n": int(len(g)),
                "kapsam_80": round(float(g["in_80"].astype(bool).mean()), 3),
                "ortalama_pinball": round(float(g["pinball"].mean()), 3),
                "yon_isabeti": round(float(dir_vals.astype(bool).mean()), 3) if len(dir_vals) else None,
            }
        out["ufuk_bazinda"] = by_h
    return out
