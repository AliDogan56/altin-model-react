import csv
import math
from datetime import date, timedelta

import pytest

from app.services import xau_dataset_service as module
from app.services.data_quality import (DataQualityError, assert_promotion_ready, feature_vector,
                                      load_dataset_manifest, validate_bars, validate_dataset_rows)
from app.services.feature_service import latest_features
from app.services.xau_dataset_service import FEATURES, FRED_IDS, Series, XauBar, build_rows


def fixture_rows():
    start = date(2024, 1, 1)
    bars = [XauBar(start + timedelta(days=i), 2030 + i * 2, 1980 + i * 2, 2000 + i * 2)
            for i in range(100)]
    macro = {name: Series([(start - timedelta(days=400), 100 + j)] +
                          [(start + timedelta(days=i), 101 + j + i / 20) for i in range(100)])
             for j, name in enumerate(FRED_IDS)}
    return bars, macro, build_rows(bars, macro)


def save(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_all_19_canonical_training_serving_features_are_identical(tmp_path):
    from app.services.trainer import _load_dataset
    _, _, rows = fixture_rows()
    path = tmp_path / "fixture.csv"
    save(path, rows)
    trained_rows, training_x = _load_dataset(path)
    live = latest_features(path)
    assert len(FEATURES) == 19
    assert live["date"] == trained_rows[-1]["date"]
    assert live["price"] == float(trained_rows[-1]["xauusd_close"])
    for index, name in enumerate(FEATURES):
        assert abs(training_x[-1, index] - live["features"][name]) < 1e-12, name
        assert abs(feature_vector(rows[-1])[index] - live["features"][name]) < 1e-12, name
    assert live["validation_status"] == "UNVERIFIED_PROVENANCE"


def test_future_bars_and_macro_observations_do_not_change_past_features():
    bars, macro, rows = fixture_rows()
    cutoff = bars[80].day
    historical = build_rows(bars[:81], macro)[-1]
    future_bars = bars[:81] + [XauBar(bar.day, bar.high * 4, bar.low * 4, bar.close * 4)
                              for bar in bars[81:]]
    future_macro = {name: Series(list(zip(series.days, series.values)) +
                                [(bars[-1].day + timedelta(days=2), 9999)])
                    for name, series in macro.items()}
    result = next(row for row in build_rows(future_bars, future_macro) if row["date"] == cutoff.isoformat())
    assert feature_vector(historical) == feature_vector(result)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), "bad", None])
def test_nonfinite_or_invalid_feature_rejected(value):
    _, _, rows = fixture_rows()
    rows[-1][FEATURES[3]] = value
    with pytest.raises(DataQualityError, match=FEATURES[3]):
        validate_dataset_rows(rows)


@pytest.mark.parametrize("field,value", [("xauusd_close", 0), ("xauusd_close", -4),
    ("date", "2024-02-30"), ("target_return_7d", -1), ("target_return_14d", math.inf)])
def test_invalid_dataset_fields_rejected(field, value):
    _, _, rows = fixture_rows()
    rows[-1][field] = value
    with pytest.raises(DataQualityError):
        validate_dataset_rows(rows)


def test_duplicate_and_out_of_order_rows_rejected():
    bars, _, rows = fixture_rows()
    for wrong in (rows + [rows[-1]], list(reversed(rows))):
        with pytest.raises(DataQualityError, match="duplicate or out-of-order"):
            validate_dataset_rows(wrong)
    for wrong in (bars + [bars[-1]], list(reversed(bars))):
        with pytest.raises(DataQualityError):
            validate_bars(wrong)


@pytest.mark.parametrize("high,low,close", [(100, 110, 105), (100, 90, 101),
    (100, 0, 95), (math.inf, 90, 95), (100, 90, float("nan"))])
def test_invalid_ohlc_rejected(high, low, close):
    with pytest.raises(DataQualityError):
        validate_bars([XauBar(date(2024, 1, 1), high, low, close)])


def test_atomic_write_keeps_old_dataset_on_validation_failure_and_records_proxy(tmp_path, monkeypatch):
    _, _, rows = fixture_rows()
    path = tmp_path / "dataset.csv"
    provenance = {"availability": "unverified", "macro_vintage": "current_revision",
                  "price_source": "yahoo:GC=F", "price_instrument": "GC=F_futures_proxy", "validated": False}
    monkeypatch.setattr(module, "fetch_dataset_with_provenance", lambda: (rows, provenance))
    assert module.write_csv(path) == len(rows)
    original = path.read_bytes()
    manifest = load_dataset_manifest(path)
    assert manifest["provenance"]["price_instrument"] == "GC=F_futures_proxy"
    assert latest_features(path)["dataset_hash"] == manifest["dataset_sha256"]
    with pytest.raises(DataQualityError, match="Promotion blocked"):
        assert_promotion_ready(path)
    rows[-1][FEATURES[0]] = math.nan
    with pytest.raises(DataQualityError):
        module.write_csv(path)
    assert path.read_bytes() == original
    assert len(list(tmp_path.iterdir())) == 2  # no abandoned temporary file


def test_tampered_manifest_snapshot_fails_closed(tmp_path, monkeypatch):
    _, _, rows = fixture_rows()
    path = tmp_path / "dataset.csv"
    monkeypatch.setattr(module, "fetch_dataset_with_provenance", lambda: (rows, {}))
    module.write_csv(path)
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(DataQualityError, match="hash mismatch"):
        latest_features(path)
