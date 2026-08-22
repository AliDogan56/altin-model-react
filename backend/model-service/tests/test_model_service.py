from types import SimpleNamespace

import numpy as np
from app.services.model_service import model_service
from app.services.xau_dataset_service import FEATURES


def test_xau_model_predicts_independent_horizons(monkeypatch):
    class Network:
        def predict(self, value): return np.array([0.01])
    state = {h: {"networks": [Network()], "x_mean": np.zeros(len(FEATURES)),
                 "x_std": np.ones(len(FEATURES)), "weight": 1.0, "error80": 0.03,
                 "training_volatility": 1.0} for h in (7, 14, 30)}
    monkeypatch.setattr(model_service, "active", {"per_horizon": state})
    result = model_service.predict(dict.fromkeys(FEATURES, 0.0), 2500)
    assert result["horizons"] == [7, 14, 30]
    assert len(result["mean"]) == 3
    assert all(value > 0 for value in result["prices"])
    assert set(result["feature_effects"]) == {"7", "14", "30"}
    assert set(result["feature_effects"]["30"]) == set(FEATURES)


def test_reload_rejects_artifact_with_mismatched_schema(tmp_path, monkeypatch):
    """D3: şeması uymayan artefakt yüklenirse predict anlamsız sonuç/500 üretir."""
    import joblib
    from app.services import model_service as module

    stale = tmp_path / "stale.joblib"
    joblib.dump({"version": "eski", "features": ["a", "b"], "horizons": [7, 14, 30],
                 "per_horizon": {}}, stale)
    service = module.ModelService.__new__(module.ModelService)
    service.active, service.version = None, "x"
    monkeypatch.setattr(module, "BUNDLED_MODEL", stale)
    monkeypatch.setattr(module, "settings", SimpleNamespace(model_dir=tmp_path / "yok"))
    service.reload()
    assert service.active is None
    assert service.rejected


def test_reload_accepts_matching_schema(tmp_path, monkeypatch):
    import joblib
    from app.services import model_service as module
    from app.services.xau_dataset_service import FEATURES, HORIZONS

    good = tmp_path / "good.joblib"
    joblib.dump({"version": "yeni", "features": list(FEATURES), "horizons": list(HORIZONS),
                 "per_horizon": {}}, good)
    service = module.ModelService.__new__(module.ModelService)
    service.active, service.version = None, "x"
    monkeypatch.setattr(module, "BUNDLED_MODEL", good)
    monkeypatch.setattr(module, "settings", SimpleNamespace(model_dir=tmp_path / "yok"))
    service.reload()
    assert service.version == "yeni"
    assert not service.rejected


def test_predict_reports_clipped_features(monkeypatch):
    """Eğitim aralığının çok dışındaki girdi kırpılıyor; çağıran bunu görmeli."""
    class Network:
        def predict(self, value): return np.array([0.01])
    state = {h: {"networks": [Network()], "x_mean": np.zeros(len(FEATURES)),
                 "x_std": np.ones(len(FEATURES)), "weight": 1.0, "error80": 0.03,
                 "training_volatility": 1.0} for h in (7, 14, 30)}
    monkeypatch.setattr(model_service, "active", {"per_horizon": state})
    values = dict.fromkeys(FEATURES, 0.0)
    values[FEATURES[2]] = 99.0
    result = model_service.predict(values, 2500)
    assert result["clipped_features"] == [FEATURES[2]]
    assert model_service.predict(dict.fromkeys(FEATURES, 0.0), 2500)["clipped_features"] == []


def test_predict_exposes_horizon_weights(monkeypatch):
    """D14: ağırlığı kısılmış ufuk, sıfıra yakın tahmini 'görüş' gibi sunulmamalı."""
    class Network:
        def predict(self, value): return np.array([0.02])
    weights = {7: 0.9, 14: 0.05, 30: 0.6}
    state = {h: {"networks": [Network()], "x_mean": np.zeros(len(FEATURES)),
                 "x_std": np.ones(len(FEATURES)), "weight": weights[h], "error80": 0.03,
                 "training_volatility": 1.0} for h in (7, 14, 30)}
    monkeypatch.setattr(model_service, "active", {"per_horizon": state})
    result = model_service.predict(dict.fromkeys(FEATURES, 0.0), 2500)
    assert result["weights"] == [0.9, 0.05, 0.6]
    assert result["confident"] == [True, False, True]
