import numpy as np
import pandas as pd

from app.services.technical.indicators import atr
from app.services.technical.levels import compute_levels, merge_levels, round_levels
from app.services.technical.resample import to_monthly, to_weekly
from app.services.technical.trendlines import compute_trend, fractal_swings, regression_channel


def zigzag_ohlc(n=300):
    idx = pd.bdate_range("2024-01-01", periods=n)
    t = np.arange(n)
    close = 3000 + 2.0 * t + 80 * np.sin(t / 12)
    return pd.DataFrame({"open": close, "high": close + 5, "low": close - 5, "close": close, "volume": 1.0}, index=idx)


def test_fractal_swings_alternate_and_are_confirmed():
    df = zigzag_ohlc()
    sw = fractal_swings(df, 5)
    assert len(sw) > 6
    assert sw["idx"].max() <= len(df) - 6
    assert set(sw["kind"]) == {"tepe", "dip"}


def test_regression_channel_recovers_slope():
    n = 250
    close = pd.Series(100 * np.exp(0.001 * np.arange(n)))
    ch = regression_channel(close, 250)
    assert abs(ch["egim_gunluk_pct"] - 0.1) < 1e-3
    assert ch["r2"] > 0.999
    assert ch["alt_2s"] <= ch["orta"] <= ch["ust_2s"]


def test_trend_and_levels_end_to_end():
    df = zigzag_ohlc()
    as_of = df.index[-1] + pd.Timedelta(days=3)
    a = float(atr(df).iloc[-1])
    trend = compute_trend(df, a, as_of)
    assert trend["dow"]["durum"] in ("yukselis", "dusus", "yatay", "belirsiz")
    assert trend["trend_cizgileri"]["destek"] is not None
    lv = compute_levels(df, to_weekly(df, as_of), to_monthly(df, as_of), a, 0.99, as_of)
    price = lv["referans"]["vadeli_kapanis"]
    assert all(x["vadeli"] > price for x in lv["direnc"])
    assert all(x["vadeli"] < price for x in lv["destek"])
    assert lv["direnc"] == sorted(lv["direnc"], key=lambda x: x["vadeli"])
    assert lv["destek"] == sorted(lv["destek"], key=lambda x: -x["vadeli"])
    for x in lv["direnc"] + lv["destek"]:
        assert abs(x["spot_esdeger"] / x["vadeli"] - 0.99) < 1e-4


def test_merge_and_round_levels():
    cands = [{"fiyat": 100.0, "kaynak": "a", "agirlik": 1.0, "yakinlik": 1.0}, {"fiyat": 100.4, "kaynak": "b", "agirlik": 1.0, "yakinlik": 0.5}, {"fiyat": 130.0, "kaynak": "c", "agirlik": 1.0, "yakinlik": 1.0}]
    m = merge_levels(cands, tol=1.0)
    assert len(m) == 2 and m[0]["kaynak_sayisi"] == 2 and abs(m[0]["puan"] - 1.5) < 1e-9
    r = round_levels(4400.0)
    assert {x["fiyat"] for x in r} >= {4200.0, 4300.0, 4400.0, 4500.0, 4600.0}
