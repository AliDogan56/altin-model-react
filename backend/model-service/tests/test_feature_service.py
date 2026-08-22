"""D1: servis, tahmin girdilerini eğitim setiyle aynı formülden vermeli."""
import csv

import pytest

from app.services import feature_service as module
from app.services.xau_dataset_service import FEATURES


def _write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _row(day: str, close: float, value: float = 0.5):
    row = {"date": day, "xauusd_close": close}
    row.update({name: value for name in FEATURES})
    row.update({"target_return_7d": "", "target_return_14d": "", "target_return_30d": ""})
    return row


def test_latest_returns_last_dataset_row(tmp_path):
    path = tmp_path / "set.csv"
    _write(path, [_row("2026-08-20", 4500.0, 0.1), _row("2026-08-21", 4684.8, 0.2)])
    result = module.latest_features(path)
    assert result["date"] == "2026-08-21"
    assert result["price"] == 4684.8
    assert set(result["features"]) == set(FEATURES)
    assert result["features"][FEATURES[0]] == 0.2


def test_latest_rejects_dataset_missing_a_feature(tmp_path):
    path = tmp_path / "set.csv"
    row = _row("2026-08-21", 4684.8)
    row.pop(FEATURES[3])
    _write(path, [row])
    with pytest.raises(ValueError, match=FEATURES[3]):
        module.latest_features(path)


def test_latest_rejects_empty_dataset(tmp_path):
    path = tmp_path / "set.csv"
    path.write_text("date,xauusd_close\n", encoding="utf-8")
    with pytest.raises(ValueError):
        module.latest_features(path)
