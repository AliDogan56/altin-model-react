from types import SimpleNamespace
from app.services import automatic_learning_service as module


def test_refresh_waits_for_twenty_new_completed_rows(monkeypatch):
    service = module.AutomaticLearningService()
    monkeypatch.setattr(module, "write_csv", lambda path: 1019)
    monkeypatch.setattr(module.model_service, "active", {"dataset_rows": 1000})
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        auto_train=True, retrain_every_new_rows=20, retrain_minimum_rows=300))
    called = []
    monkeypatch.setattr(module, "train_model", lambda **_: called.append(True))
    result = service._refresh_and_train()
    assert result == {"training_rows": 1019, "trained": False}
    assert not called


def test_refresh_retrains_after_twenty_new_completed_rows(monkeypatch):
    service = module.AutomaticLearningService()
    monkeypatch.setattr(module, "write_csv", lambda path: 1020)
    monkeypatch.setattr(module.model_service, "active", {"dataset_rows": 1000})
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        auto_train=True, retrain_every_new_rows=20, retrain_minimum_rows=300))
    monkeypatch.setattr(module, "train_model", lambda **_: {"version": "new"})
    reloaded = []
    monkeypatch.setattr(module.model_service, "reload", lambda: reloaded.append(True))
    assert service._refresh_and_train() == {"version": "new"}
    assert reloaded


def test_job_honours_retrain_minimum_rows(monkeypatch):
    """D4: RETRAIN_MINIMUM_ROWS otomatik yolda da geçerli olmalı."""
    service = module.AutomaticLearningService()
    monkeypatch.setattr(module, "write_csv", lambda path: 1200)
    monkeypatch.setattr(module.model_service, "active", {"dataset_rows": 1000})
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        auto_train=True, retrain_every_new_rows=20, retrain_minimum_rows=777))
    seen = {}
    monkeypatch.setattr(module, "train_model", lambda **kwargs: seen.update(kwargs) or {"version": "v"})
    monkeypatch.setattr(module.model_service, "reload", lambda: None)
    service._refresh_and_train()
    assert seen["minimum_rows"] == 777


def test_job_reports_dataset_rows_when_not_training(monkeypatch):
    service = module.AutomaticLearningService()
    monkeypatch.setattr(module, "write_csv", lambda path: 1001)
    monkeypatch.setattr(module.model_service, "active", {"dataset_rows": 1000})
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        auto_train=True, retrain_every_new_rows=20, retrain_minimum_rows=300))
    result = service._refresh_and_train()
    assert result == {"training_rows": 1001, "trained": False}
    assert service.last_result == result
