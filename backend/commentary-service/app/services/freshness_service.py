"""Veri tazeliği raporu: her serinin son gözlemi, yaşı ve kaynağı. Bayat veri gizlenmez, yazılır."""
from __future__ import annotations

import pandas as pd

from ..market_constants import FRED_SERIES


def freshness_report(prices: pd.DataFrame, market: pd.DataFrame | None, macro: pd.DataFrame | None, as_of: pd.Timestamp, macro_errors: dict | None = None) -> dict:
    def age(d):
        return int((as_of - pd.Timestamp(d)).days)

    spot = prices.dropna(subset=["spot_close"])
    fut = prices[prices["fut_close"].notna() & ~prices["partial"]]
    out = {
        "as_of": as_of.strftime("%Y-%m-%d"),
        "fiyat": {
            "spot_lbma_pm": {"son": spot["date"].iloc[-1].strftime("%Y-%m-%d"), "yas_gun": age(spot["date"].iloc[-1]), "satir": int(len(spot)), "deger": float(spot["spot_close"].iloc[-1])},
            "vadeli_gcf": {"son_tamamlanan": fut["date"].iloc[-1].strftime("%Y-%m-%d"), "yas_gun": age(fut["date"].iloc[-1]), "satir": int(len(fut)), "deger": float(fut["fut_close"].iloc[-1]), "bugun_kismi_bar_var": bool(prices["partial"].any())},
            "basis_son": float(prices["basis"].dropna().iloc[-1]),
        },
        "uyarilar": [],
    }
    if out["fiyat"]["spot_lbma_pm"]["yas_gun"] > 4:
        out["uyarilar"].append("LBMA PM fiksi 4 günden eski.")
    if market is not None and len(market):
        out["piyasa"] = {}
        for col in market.columns:
            if col == "date":
                continue
            s = market.dropna(subset=[col])
            out["piyasa"][col] = {"son": s["date"].iloc[-1].strftime("%Y-%m-%d"), "yas_gun": age(s["date"].iloc[-1]), "deger": float(s[col].iloc[-1])}
    if macro is not None and len(macro):
        out["makro"] = {}
        for sid, g in macro.groupby("series"):
            g = g.sort_values("obs_date")
            known = g[g["available_at"] <= as_of]
            last = known.iloc[-1] if len(known) else g.iloc[-1]
            out["makro"][sid] = {
                "aciklama": FRED_SERIES.get(sid, {}).get("desc", ""),
                "son_gozlem": pd.Timestamp(last["obs_date"]).strftime("%Y-%m-%d"),
                "yas_gun": age(last["obs_date"]),
                "deger": float(last["value"]),
                "kaynak": str(last["source"]),
                "as_of_itibariyla_biliniyor": bool(len(known)),
            }
    for sid in FRED_SERIES:
        if macro is None or sid not in set(macro["series"]):
            out["uyarilar"].append(f"{sid} alınamadı" + (f": {macro_errors[sid]}" if macro_errors and sid in macro_errors else ""))
    return out
