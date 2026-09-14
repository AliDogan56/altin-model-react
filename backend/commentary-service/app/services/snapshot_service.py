"""Piyasa anlık görüntüsü: fiyat + makro verileri tazeler, teknik hesapları yapar, DATA_DIR/latest/*.json yazar.

Ajan istemleri bu JSON'ları okur; anahtarlar Türkçedir çünkü model Türkçe yazar (API sözleşmesi ise İngilizcedir,
bkz. commentary_store). Sayılar yalnız buradan gelir; hiçbir LLM sayı üretmez.
"""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd

from ..market_constants import LATEST_DIR, MACRO_CSV, MARKET_CSV, PRICES_CSV
from . import forecast_ledger as ledger
from . import live_price_service as live_mod
from . import macro_data_service as fred
from . import price_data_service as prices_mod
from .base_cone import base_cone
from .freshness_service import freshness_report
from .technical.indicators import atr
from .technical.levels import compute_levels
from .technical.momentum import compute_momentum
from .technical.resample import to_monthly, to_weekly
from .technical.trendlines import compute_trend


def _dump(name: str, payload: dict) -> None:
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    with open(LATEST_DIR / name, "w") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)


def load_latest(name: str):
    path = LATEST_DIR / name
    return json.loads(path.read_text()) if path.exists() else None


def build_snapshot(offline: bool = False, as_of: str | None = None) -> dict:
    """Veriyi tazeler (offline değilse) ve anlık görüntüyü döndürür; ara ürünler latest/ altına yazılır."""
    as_of_ts = pd.Timestamp(as_of) if as_of else pd.Timestamp(dt.datetime.now(dt.UTC).date())
    log = {"as_of": str(as_of_ts.date()), "steps": {}}
    macro_errors: dict = {}
    if not offline:
        try:
            prices = prices_mod.update_prices()
            log["steps"]["prices"] = "ok"
        except Exception as error:  # noqa: BLE001
            log["steps"]["prices"] = f"ERROR {error}"
            if not PRICES_CSV.exists():
                raise
            prices = prices_mod.load_prices()
        try:
            market = prices_mod.update_market()
            log["steps"]["market"] = "ok" + (f" (missing: {market.attrs.get('errors')})" if market.attrs.get("errors") else "")
        except Exception as error:  # noqa: BLE001
            log["steps"]["market"] = f"ERROR {error}"
            market = pd.read_csv(MARKET_CSV, parse_dates=["date"]) if MARKET_CSV.exists() else None
        try:
            macro, macro_errors = fred.update_macro_store()
            log["steps"]["macro"] = "ok" + (f" (missing: {list(macro_errors)})" if macro_errors else "")
        except Exception as error:  # noqa: BLE001
            log["steps"]["macro"] = f"ERROR {error}"
            macro = fred.load_macro() if MACRO_CSV.exists() else None
    else:
        prices = prices_mod.load_prices()
        market = pd.read_csv(MARKET_CSV, parse_dates=["date"]) if MARKET_CSV.exists() else None
        macro = fred.load_macro() if MACRO_CSV.exists() else None
        log["steps"]["data"] = "offline"

    daily = prices_mod.futures_ohlc(prices)
    weekly, monthly = to_weekly(daily, as_of_ts), to_monthly(daily, as_of_ts)
    atr_last = float(atr(daily).iloc[-1])
    basis = float(prices["basis"].dropna().iloc[-20:].median())  # 20 günlük medyan: fiks/vadeli zamanlama gürültüsünü bastırır

    momentum = compute_momentum(daily, weekly, monthly, as_of_ts)
    trend = compute_trend(daily, atr_last, as_of_ts, basis=basis)
    levels = compute_levels(daily, weekly, monthly, atr_last, basis, as_of_ts)
    fresh = freshness_report(prices, market, macro, as_of_ts, macro_errors)
    spot = prices_mod.spot_series(prices)

    live = {"canli_spot": None, "hatalar": {"canli": "offline"}}
    if not offline:
        try:
            live = live_mod.live_snapshot(spot.index[-1], float(spot.iloc[-1]), atr_last, basis)
        except Exception as error:  # noqa: BLE001
            live = {"canli_spot": None, "hatalar": {"canli": str(error)}}
    levels["canli"] = live_mod.levels_vs_live(levels, live["canli_spot"]["fiyat"], levels["referans"]["test_marji"] * basis) if live.get("canli_spot") else None

    resolved = ledger.resolve(spot, as_of_ts)
    ledger_summary = ledger.summary()
    ledger_summary["resolved_this_run"] = len(resolved)
    cone = base_cone(spot, as_of_ts)

    def pct(n):
        return round((spot.iloc[-1] / spot.iloc[-1 - n] - 1) * 100, 2) if len(spot) > n else None

    snapshot = {
        "as_of": str(as_of_ts.date()),
        "spot_lbma_pm": {"tarih": spot.index[-1].strftime("%Y-%m-%d"), "fiyat": float(spot.iloc[-1]), "degisim_pct": {"1g": pct(1), "5g": pct(5), "21g": pct(21), "63g": pct(63), "126g": pct(126), "252g": pct(252)}},
        "vadeli_gcf": {"son_tamamlanan_bar": daily.index[-1].strftime("%Y-%m-%d"), "kapanis": float(daily["close"].iloc[-1]), "atr14": round(atr_last, 2), "atr14_pct": round(atr_last / float(daily["close"].iloc[-1]) * 100, 2)},
        "basis": round(basis, 5),
        "canli": live.get("canli_spot"),
        "canli_zaman_utc": live.get("zaman_utc"),
        "momentum": {k: {"skor": v["skor"], "etiket": v["etiket"]} for k, v in momentum["cerceveler"].items()},
        "hizalanma": momentum["hizalanma"]["durum"],
        "dow": trend["dow"]["durum"],
        "makro_son": fred.latest_values(macro, as_of_ts)["value"].round(3).to_dict() if macro is not None and len(macro) else {},
        "uyarilar": fresh["uyarilar"],
    }
    for name, payload in (("live.json", live), ("base_cone.json", cone), ("momentum.json", momentum), ("trend.json", trend), ("levels.json", levels), ("freshness.json", fresh), ("ledger_summary.json", ledger_summary), ("snapshot.json", snapshot), ("run_log.json", log)):
        _dump(name, payload)
    return snapshot
