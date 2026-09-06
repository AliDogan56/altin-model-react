"""A rolling dataset refresh prepares candidates without replacing the champion."""
import hashlib
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from app.services import automatic_learning_service as module


@pytest.fixture
def setup(monkeypatch, tmp_path):
    service = module.AutomaticLearningService()
    path = tmp_path / "snapshot.csv"
    path.write_text("immutable test snapshot")
    rows = [{"date": (date(2026, 1, 1) + timedelta(days=i)).isoformat(),
             **{f"target_return_{h}d": ".01" for h in (7, 14, 30)}} for i in range(40)]
    monkeypatch.setattr(module, "DATASET", path)
    monkeypatch.setattr(module, "write_csv", lambda _: len(rows))
    monkeypatch.setattr(module, "_load_dataset", lambda _: (rows, None))
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        auto_train=True, retrain_every_new_rows=5, retrain_minimum_rows=777, model_dir=tmp_path))
    active = {"dataset_rows": 40, "training_end": {str(h): rows[-6]["date"] for h in (7, 14, 30)}}
    monkeypatch.setattr(module.model_service, "active", active)
    calls, reloads = [], []
    def train(**kwargs):
        calls.append(kwargs)
        return {"version": "candidate", "dataset_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
                "training_end": {str(h): rows[-1]["date"] for h in (7, 14, 30)}}
    monkeypatch.setattr(module, "train_model", train)
    monkeypatch.setattr(module.model_service, "reload", lambda: reloads.append(True))
    return service, rows, active, calls, reloads


def test_rolling_same_row_count_retrains_matured_labels(setup):
    service, _, _, calls, reloads = setup
    result = service._refresh_and_train()
    assert result["trained"] is True
    assert result["promoted"] is False
    assert calls[0]["minimum_rows"] == 777
    assert calls[0]["promote"] is False
    assert not reloads


def test_same_snapshot_not_retrained_repeatedly(setup):
    service, _, _, calls, _ = setup
    service._refresh_and_train()
    assert service._refresh_and_train()["trained"] is False
    assert len(calls) == 1


def test_waits_for_new_matured_labels_not_unlabelled_rows(setup):
    service, rows, _, calls, _ = setup
    for row in rows[-5:]:
        row["target_return_30d"] = ""
    result = service._refresh_and_train()
    assert result["trained"] is False
    assert result["new_labels_by_horizon"]["30"] == 0
    assert not calls


def test_cold_start_creates_candidate_but_never_promotes(setup, monkeypatch):
    service, _, _, calls, reloads = setup
    monkeypatch.setattr(module.model_service, "active", None)
    assert service._refresh_and_train()["promoted"] is False
    assert calls and not reloads


def test_disabled_auto_training_does_not_train(setup, monkeypatch):
    service, _, _, calls, _ = setup
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        auto_train=False, retrain_every_new_rows=5, retrain_minimum_rows=300, model_dir=module.DATASET.parent))
    assert service._refresh_and_train()["trained"] is False
    assert not calls
