import numpy as np
import pandas as pd

from app.services.technical.momentum import alignment, compute_momentum, label, scale_score
from app.services.technical.resample import to_monthly, to_weekly
from tests.test_indicators import synthetic_ohlc


def test_scale_score_saturates_and_keeps_sign():
    s = pd.Series(np.concatenate([np.random.default_rng(1).normal(0, 1, 300), [10.0]]))
    v, sc = scale_score(s, 252)
    assert v == 10.0 and sc == 1.0
    s2 = pd.Series(np.concatenate([np.random.default_rng(1).normal(0, 1, 300), [-0.5]]))
    _, sc2 = scale_score(s2, 252)
    assert -1 < sc2 < 0


def test_labels():
    assert label(75) == "güçlü yükseliş" and label(-30) == "düşüş" and label(0) == "nötr"


def test_uptrend_scores_positive_and_aligned():
    n = 1500
    idx = pd.bdate_range("2019-01-01", periods=n)
    close = 1500 * np.exp(np.cumsum(np.full(n, 0.0012) + np.random.default_rng(3).normal(0, 0.004, n)))
    df = pd.DataFrame({"open": close, "high": close * 1.004, "low": close * 0.996, "close": close, "volume": 1.0}, index=idx)
    as_of = idx[-1] + pd.Timedelta(days=3)
    m = compute_momentum(df, to_weekly(df, as_of), to_monthly(df, as_of), as_of)
    assert m["cerceveler"]["gunluk"]["skor"] > 20
    assert m["cerceveler"]["aylik"]["skor"] > 20
    assert m["hizalanma"]["durum"] in ("hizali_yukselis", "karisik")


def test_alignment_correction_case():
    assert alignment(-40, 10, 50)["durum"] == "yukselis_icinde_duzeltme"
    assert alignment(30, 30, 30)["durum"] == "hizali_yukselis"


def test_resample_drops_incomplete_period():
    df = synthetic_ohlc(n=60)
    last = df.index[-1]
    w_mid = to_weekly(df, last)  # as_of hafta ortasında: son hafta tamamlanmamış
    w_done = to_weekly(df, last + pd.Timedelta(days=7))
    assert len(w_done) == len(w_mid) + 1
