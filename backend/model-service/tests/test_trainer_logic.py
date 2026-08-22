"""D5–D9: eğitim hattının sağlamlık ve tutarlılık kuralları."""
import csv

import numpy as np
import pytest

from app.services import trainer as module
from app.services.xau_dataset_service import FEATURES, HORIZONS


def test_dataset_missing_column_reports_the_name(tmp_path):
    """D5: eski şemalı CSV, anlamsız KeyError yerine adı geçen hata vermeli."""
    path = tmp_path / "set.csv"
    columns = ["date", "xauusd_close", *[f for f in FEATURES if f != FEATURES[4]]]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerow({name: 0 for name in columns})
    with pytest.raises(ValueError, match=FEATURES[4]):
        module._load_dataset(path)


def test_train_model_has_no_ignored_parameters():
    """D6: yok sayılan feature_names/horizons parametreleri kalmamalı."""
    import inspect
    names = set(inspect.signature(module.train_model).parameters)
    assert "feature_names" not in names
    assert "horizons" not in names


def test_shrinkage_weight_is_the_regression_slope():
    """D8: cov(ddof=1)/var(ddof=0) karışımı ağırlığı şişiriyordu."""
    rng = np.random.default_rng(7)
    oof = rng.normal(size=400)
    actual = 0.4 * oof + rng.normal(scale=0.1, size=400)
    expected = float(np.polyfit(oof, actual, 1)[0])
    assert module._shrinkage_weight(actual, oof) == pytest.approx(expected, rel=1e-9)


def test_shrinkage_weight_is_clamped():
    oof = np.array([1.0, 2.0, 3.0, 4.0])
    assert module._shrinkage_weight(-oof, oof) == 0.0          # ters ilişki
    assert module._shrinkage_weight(5 * oof, oof) == 1.0       # 1'in üstü kırpılır
    assert module._shrinkage_weight(oof, np.zeros(4)) == 0.0   # varyans yok


def test_horizon_is_deactivated_when_served_prediction_loses_to_zero():
    """D9: karar ham beceriye, rapor ağırlıklı beceriye bakıyordu."""
    actual = np.array([0.01, -0.02, 0.03, -0.01] * 30)
    oof = -actual                                              # tamamen ters model
    weight, skill = module._weight_and_skill(actual, oof)
    assert weight == 0.0
    assert skill == 0.0


def test_horizon_stays_active_when_it_beats_zero():
    rng = np.random.default_rng(3)
    actual = rng.normal(scale=0.02, size=200)
    oof = actual + rng.normal(scale=0.005, size=200)
    weight, skill = module._weight_and_skill(actual, oof)
    assert weight > 0
    assert skill > 0


def test_training_rows_key_survives_horizon_change(monkeypatch):
    """D7: sabit "7" anahtarı, ufuk listesi değişince KeyError veriyordu."""
    assert module._primary_horizon_key({str(h): h for h in HORIZONS}) == str(HORIZONS[0])
    assert module._primary_horizon_key({"5": 1, "9": 2}, horizons=(5, 9)) == "5"
