from datetime import date, timedelta

import numpy as np
import pytest

from app.services.preprocessing import fit_scaler, transform_features
from app.services.temporal_validation import purged_walk_forward_splits, target_dates_for_rows
from app.services import trainer
from app.services.xau_dataset_service import FEATURES


def test_split_purges_actual_calendar_target_maturity():
    dates = [date(2020, 1, 1) + timedelta(days=i * 2) for i in range(900)]
    for horizon in (7, 14, 30):
        # Include a long closure beyond the nominal horizon.
        ends = [day + timedelta(days=horizon + (40 if i % 61 == 0 else 0)) for i, day in enumerate(dates)]
        folds = purged_walk_forward_splits(dates, ends)
        assert len(folds) == 3
        for fold in folds:
            assert max(ends[i] for i in fold.train) < dates[fold.calibration[0]]
            assert max(ends[i] for i in fold.calibration) < dates[fold.test[0]]
            assert not set(fold.train) & set(fold.calibration)
            assert not set(fold.calibration) & set(fold.test)


def test_target_endpoint_uses_next_observed_trading_day():
    rows = [{"date": day} for day in ("2026-01-02", "2026-01-09", "2026-01-12")]
    assert target_dates_for_rows(rows, [0], 7) == [date(2026, 1, 9)]
    rows[0]["target_date_7d"] = "2026-01-12"
    assert target_dates_for_rows(rows, [0], 7) == [date(2026, 1, 12)]
    with pytest.raises(ValueError, match="endpoint"):
        target_dates_for_rows(rows, [2], 7)


def test_target_rejects_wrong_return_and_missing_matured_label():
    rows = [{"date": "2026-01-02", "xauusd_close": 2000, "target_return_7d": .1},
            {"date": "2026-01-09", "xauusd_close": 2020, "target_return_7d": ""}]
    with pytest.raises(ValueError, match="actual future close"):
        target_dates_for_rows(rows, [0], 7)
    rows[0]["target_return_7d"] = ""
    with pytest.raises(ValueError, match="Missing matured"):
        target_dates_for_rows(rows, [], 7)
    rows[0]["target_return_7d"] = .01
    rows[1]["target_return_7d"] = .01
    with pytest.raises(ValueError, match="endpoint"):
        target_dates_for_rows(rows, [0, 1], 7)


def test_scaler_never_uses_future_extremes_and_transform_is_shared():
    train = np.array([[1., 10.], [3., 10.], [5., 10.]])
    mean, std = fit_scaler(train)
    np.testing.assert_allclose(mean, [3., 10.])
    assert std[1] == 1
    prior_mean, prior_std = mean.copy(), std.copy()
    future = transform_features(np.array([[100000., -100000.]]), mean, std)
    np.testing.assert_array_equal(future, [[6., -6.]])
    np.testing.assert_array_equal(mean, prior_mean)
    np.testing.assert_array_equal(std, prior_std)
    np.testing.assert_array_equal(transform_features(train, mean, std), transform_features(train, mean, std))


def test_outer_test_targets_never_choose_its_weight_or_interval(monkeypatch):
    count = 900
    dates = [date(2020, 1, 1) + timedelta(days=i) for i in range(count)]
    ends = [day + timedelta(days=30) for day in dates]
    rng = np.random.default_rng(91)
    x = rng.normal(size=(count, len(FEATURES)))
    x[:, FEATURES.index("gold_volatility_20d")] = .2
    y = .01 * x[:, 0] + rng.normal(scale=.001, size=count)
    def fake_fit(x_train, y_train, x_test, epochs):
        return .01 * x_test[:, 0], [], np.zeros(len(FEATURES)), np.ones(len(FEATURES))
    monkeypatch.setattr(trainer, "_fit_predict", fake_fit)
    before = trainer._walk_forward(x, y, 30, 1, dates, ends)[-1]
    changed = y.copy()
    first = purged_walk_forward_splits(dates, ends)[0]
    changed[first.test] += .5
    after = trainer._walk_forward(x, changed, 30, 1, dates, ends)[-1]
    left, right = before["folds"][0], after["folds"][0]
    assert left["weight"] == right["weight"]
    cutoff = dates[first.test[-1]].isoformat()
    for old, new in zip(before["predictions"], after["predictions"]):
        if old["date"] <= cutoff:
            assert old["served_return"] == new["served_return"]
            assert old["interval_widths"] == new["interval_widths"]
    assert left["metrics"]["mae"] != right["metrics"]["mae"]
    for fold in before["folds"]:
        assert fold["train"]["last_target"] < fold["weight_calibration"]["start"]
        assert fold["weight_calibration"]["last_target"] < fold["interval_calibration"]["start"]
        assert fold["interval_calibration"]["last_target"] < fold["test"]["start"]
