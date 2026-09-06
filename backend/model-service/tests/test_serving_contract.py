from datetime import datetime, timedelta, timezone
import json
import sqlite3
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.models.api_models import PredictIn
from app.services.model_service import ModelService
from app.services.prediction_ledger import PredictionLedger
from app.services.prediction_service import PredictionService
from app.services.xau_dataset_service import FEATURES, HORIZONS


class LinearNetwork:
    def predict(self, x):
        return np.asarray(x)[:, 0] * .01


def service():
    model = ModelService.__new__(ModelService)
    model.version, model.rejected = "test-v1", []
    model.active = {"version": "test-v1", "features": list(FEATURES), "horizons": list(HORIZONS),
        "per_horizon": {h: {"networks": [LinearNetwork()], "x_mean": np.zeros(len(FEATURES)),
            "x_std": np.ones(len(FEATURES)), "weight": .5 if h != 14 else 0.0,
            "error80": .04, "training_volatility": .2} for h in HORIZONS}}
    return model


def features():
    return {**dict.fromkeys(FEATURES, 0.0), FEATURES[0]: .5, "gold_volatility_20d": .2}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_input_finite_on_api_and_direct_serving(value):
    with pytest.raises(ValidationError):
        PredictIn(price=value, features=features())
    with pytest.raises(ValidationError):
        PredictIn(price=4500, features={**features(), FEATURES[0]: value})
    with pytest.raises(ValueError):
        service().predict({**features(), FEATURES[0]: value}, 4500)


def test_legacy_numerics_deterministic_and_coverage_not_claimed_calibrated():
    model = service()
    first = model.predict(features(), 4500)
    assert first == model.predict(features(), 4500)
    assert first["mean"] == pytest.approx([.0025, 0, .0025])
    assert first["error"] == pytest.approx([.04, .04, .04])
    assert first["intervals"][0]["nominal_coverage"] == .8
    assert first["intervals"][0]["empirical_coverage"] is None
    assert first["no_view_reasons"][1] == ["historical_weight_below_threshold"]


def test_new_pipeline_does_not_silently_neutralize_but_legacy_does():
    model = service()
    assert model.predict(features(), 4500, (FEATURES[0],))["mean"][0] == 0
    model.active["input_policy"] = "canonical-asof-no-neutralization-v1"
    assert model.predict(features(), 4500, (FEATURES[0],))["mean"][0] == pytest.approx(.0025)


def test_ood_is_unvalidated_diagnostic_not_a_fake_confidence_reweight():
    result = service().predict({**features(), FEATURES[0]: 9}, 4500)
    assert result["status"] == "OUT_OF_DISTRIBUTION"
    assert result["weights"] == [.5, 0, .5]
    assert result["ood"]["threshold_validated"] is False


def test_full_request_uses_one_artifact_snapshot_during_reload():
    model = service()
    new_artifact = service().active
    new_artifact["version"] = "replacement"
    for state in new_artifact["per_horizon"].values():
        state["weight"] = .1
    class ReloadingNetwork(LinearNetwork):
        def predict(self, x):
            model.active, model.version = new_artifact, "replacement"
            return super().predict(x)
    model.active["per_horizon"][7]["networks"] = [ReloadingNetwork()]
    result = model.predict(features(), 4500)
    assert result["version"] == "test-v1"
    assert result["weights"] == [.5, 0, .5]


def test_schema_rejects_corrupt_scaler_and_accepts_complete_legacy():
    model = service()
    assert model._schema_error(model.active) is None
    model.active["per_horizon"][7]["x_std"][0] = 0
    assert model._schema_error(model.active) is not None


def test_admin_mutations_fail_closed(monkeypatch):
    from app.controllers import admin_auth
    monkeypatch.setattr(admin_auth, "settings", SimpleNamespace(admin_token=""))
    with pytest.raises(HTTPException) as error:
        admin_auth.require_admin(None)
    assert error.value.status_code == 503
    monkeypatch.setattr(admin_auth, "settings", SimpleNamespace(admin_token="test-only-secret"))
    with pytest.raises(HTTPException) as error:
        admin_auth.require_admin("Bearer invalid")
    assert error.value.status_code == 401
    admin_auth.require_admin("Bearer test-only-secret")


def test_client_cannot_create_official_forecast(monkeypatch):
    from app.services import prediction_service as module
    monkeypatch.setattr(module, "latest_features", lambda: {"provenance": {"validated": False}})
    with pytest.raises(ValueError, match="UNVERIFIED_PROVENANCE"):
        PredictionService().canonical()


def test_unknown_or_stale_source_disables_view_without_changing_returns(monkeypatch):
    from app.services import prediction_service as module
    monkeypatch.setattr(module, "model_service", service())
    monkeypatch.setattr(module, "frozen_now", lambda: ())
    monkeypatch.setattr(module, "settings", SimpleNamespace(prediction_logging=False))
    predictor = PredictionService()
    today = datetime.now(timezone.utc).date()
    current = predictor.predict(PredictIn(price=4500, features=features(), source_date=today))
    unknown = predictor.predict(PredictIn(price=4500, features=features()))
    stale = predictor.predict(PredictIn(price=4500, features=features(), source_date=today-timedelta(days=8)))
    assert current["status"] == "OK"
    assert unknown["status"] == "INSUFFICIENT_DATA"
    assert stale["status"] == "STALE_DATA"
    assert stale["confident"] == unknown["confident"] == [False, False, False]
    assert current["mean"] == stale["mean"] == unknown["mean"]
    assert current["forecast_kind"] == "client_scenario"
    assert stale["origin_date"] == today.isoformat()
    assert stale["feature_source_date"] != stale["origin_date"]
    with pytest.raises(ValueError, match="future"):
        predictor.predict(PredictIn(price=4500, features=features(), source_date=today+timedelta(days=1)))


def test_training_route_rejects_unauthenticated_calls_before_training(monkeypatch):
    from app.controllers import admin_auth, learning_controller
    called = []
    monkeypatch.setattr(admin_auth, "settings", SimpleNamespace(admin_token="test-token"))
    monkeypatch.setattr(learning_controller.learning_service, "train", lambda _: called.append(True) or {"candidate": True})
    app = FastAPI()
    app.include_router(learning_controller.router, prefix="/v1")
    with TestClient(app) as client:
        assert client.post("/v1/training/run", json={}).status_code == 401
        assert not called
        response = client.post("/v1/training/run", json={}, headers={"Authorization": "Bearer test-token"})
        assert response.status_code == 200 and response.json()["candidate"] is True


def forecast_body():
    result = service().predict(features(), 4500)
    result.update({"prediction_timestamp": "2024-01-01T22:00:00+00:00", "origin_date": "2024-01-01"})
    return result


def test_ledger_read_is_nonmutating_and_scenarios_excluded(tmp_path):
    ledger = PredictionLedger(tmp_path / "ledger.sqlite3")
    assert ledger.monitoring()["status"] == "NO_LOGGED_PREDICTIONS"
    assert not ledger.path.exists()
    ids = ledger.append(forecast_body(), features(), kind="client_scenario", instrument="client_unspecified")
    assert len(ids) == 3
    assert ledger.monitoring()["status"] == "NO_OFFICIAL_PREDICTIONS"


def test_append_only_dedup_and_explicit_same_instrument_reconciliation(tmp_path):
    ledger = PredictionLedger(tmp_path / "ledger.sqlite3")
    ids = ledger.append(forecast_body(), features(), kind="canonical_daily", instrument="XAUUSD_spot")
    assert ids == ledger.append(forecast_body(), features(), kind="canonical_daily", instrument="XAUUSD_spot")
    args = {"actual_date": "2024-01-08", "actual_price": 4510, "instrument": "XAUUSD_spot",
            "source": "verified-test-fixture", "first_session_verified": True, "observed_at": "2024-01-09T00:00:00+00:00"}
    with pytest.raises(ValueError):
        ledger.reconcile(ids[0], **{**args, "instrument": "GC=F_futures_proxy"})
    with pytest.raises(ValueError):
        ledger.reconcile(ids[0], **{**args, "first_session_verified": False})
    ledger.reconcile(ids[0], **args)
    with pytest.raises(sqlite3.IntegrityError):
        ledger.reconcile(ids[0], **args)
    with sqlite3.connect(ledger.path) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE forecasts SET instrument='altered'")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM outcomes")
    summary = ledger.monitoring()["windows"]["XAUUSD_spot/test-v1/7d/30"]
    assert summary["resolved"] == 1
    assert summary["direction_accuracy"] == 1
    assert summary["interval_coverage"] == 1
    assert summary["mae_price"] == pytest.approx(1.25)


def test_no_retroactive_canonical_issuance_or_reconciliation(tmp_path, monkeypatch):
    ledger = PredictionLedger(tmp_path / "ledger.sqlite3")
    old = {**forecast_body(), "prediction_timestamp": "2024-01-09T00:00:00+00:00"}
    with pytest.raises(ValueError, match="before every target"):
        ledger.append(old, features(), kind="canonical_daily", instrument="XAUUSD_spot")
    # Even explicit historical scenarios cannot receive outcomes known by their
    # issuance time and later masquerade as genuinely forward observations.
    ids = ledger.append(old, features(), kind="client_scenario", instrument="client_unspecified")
    args = {"actual_date": "2024-01-08", "actual_price": 4510, "instrument": "client_unspecified",
            "source": "fixture", "first_session_verified": True}
    for observed in ("2024-01-08T23:00:00+00:00", "2024-01-09T00:00:00+00:00"):
        with pytest.raises(ValueError, match="follow forecast issuance"):
            ledger.reconcile(ids[0], **args, observed_at=observed)
    from app.services import prediction_service as module
    today = datetime.now(timezone.utc).date()
    provenance = {"validated": True, "price_instrument": "XAUUSD_spot", "availability": "point_in_time",
                  "macro_vintage": "point_in_time", "price_source": "verified-test-provider"}
    monkeypatch.setattr(module, "latest_features", lambda: {"date": (today-timedelta(days=7)).isoformat(),
        "features": features(), "price": 4500, "provenance": provenance})
    with pytest.raises(ValueError, match="RETROACTIVE_FORECAST"):
        PredictionService().canonical()


def test_canonical_settlement_requires_explicit_same_source_and_parsed_dates(tmp_path):
    ledger = PredictionLedger(tmp_path / "ledger.sqlite3")
    body = {**forecast_body(), "provenance": {"price_source": "verified-original-provider"}}
    ident = ledger.append(body, features(), kind="canonical_daily", instrument="XAUUSD_spot")[0]
    args = {"actual_date": "20240108", "actual_price": 4510, "instrument": "XAUUSD_spot",
            "first_session_verified": True, "observed_at": "2024-01-09T00:00:00+00:00"}
    with pytest.raises(ValueError, match="source must match"):
        ledger.reconcile(ident, **args, source="different-provider")
    ledger.reconcile(ident, **args, source="verified-original-provider")
    with sqlite3.connect(ledger.path) as db:
        assert db.execute("SELECT actual_date FROM outcomes").fetchone()[0] == "2024-01-08"


def test_monitoring_stratifies_versions_and_counts_only_first_daily_issuance(tmp_path):
    ledger = PredictionLedger(tmp_path / "ledger.sqlite3")
    first = forecast_body()
    ledger.append(first, features(), kind="canonical_daily", instrument="XAUUSD_spot")
    later = {**forecast_body(), "prediction_timestamp": "2024-01-01T22:01:00+00:00"}
    ledger.append(later, {**features(), FEATURES[0]: 9}, kind="canonical_daily", instrument="XAUUSD_spot")
    replacement = {**forecast_body(), "version": "test-v2", "prediction_timestamp": "2024-01-01T22:02:00+00:00"}
    ledger.append(replacement, features(), kind="canonical_daily", instrument="XAUUSD_spot")
    windows = ledger.monitoring()["windows"]
    assert len(windows) == 12  # three horizons, two windows, two models
    for version in ("test-v1", "test-v2"):
        summary = windows[f"XAUUSD_spot/{version}/7d/30"]
        assert summary["predictions"] == 1
        assert summary["model_version"] == version
    assert windows["XAUUSD_spot/test-v1/7d/30"]["feature_mean_training_z"][FEATURES[0]] == .5


def test_flat_outcome_is_not_a_directional_hit_or_miss(tmp_path):
    ledger = PredictionLedger(tmp_path / "ledger.sqlite3")
    ident = ledger.append(forecast_body(), features(), kind="canonical_daily", instrument="XAUUSD_spot")[0]
    ledger.reconcile(ident, actual_date="2024-01-08", actual_price=4500,
                     instrument="XAUUSD_spot", source="fixture", first_session_verified=True,
                     observed_at="2024-01-09T00:00:00+00:00")
    summary = ledger.monitoring()["windows"]["XAUUSD_spot/test-v1/7d/30"]
    assert summary["resolved"] == 1
    assert summary["directional_observations"] == 0
    assert summary["direction_accuracy"] is None


# Bu anahtarlar 2026-09-06 öncesi /v1/predict sözleşmesi; `scenario_zones` eklemeli.
PREVIOUS_PREDICT_KEYS = {
    "version", "source", "horizons", "mean", "error", "base_price", "prices", "clipped_features",
    "neutralized_features", "weights", "confident", "no_view_reasons", "status", "input_policy",
    "intervals", "model_disagreement", "ood", "feature_effects", "prediction_timestamp", "origin_date",
    "feature_source_date", "forecast_kind", "provenance", "input_verification", "target_dates",
    "target_date_rule", "logging"}


def test_predict_route_keeps_previous_keys_and_adds_scenario_zones_per_horizon(monkeypatch):
    from app.controllers import prediction_controller
    from app.services import prediction_service as module
    model = service()
    monkeypatch.setattr(module, "model_service", model)
    monkeypatch.setattr(prediction_controller, "model_service", model)
    monkeypatch.setattr(module, "frozen_now", lambda: ())
    monkeypatch.setattr(module, "settings", SimpleNamespace(prediction_logging=False))
    app = FastAPI()
    app.include_router(prediction_controller.router, prefix="/v1")
    today = datetime.now(timezone.utc).date()
    body = {"price": 4500, "features": {**features(), "gold_atr14_pct": .02}, "source_date": today.isoformat()}
    with TestClient(app) as client:
        response = client.post("/v1/predict", json=body)
        assert response.status_code == 200, response.text
        result = response.json()
        assert PREVIOUS_PREDICT_KEYS <= set(result)
        zones = result["scenario_zones"]
        assert list(zones) == [str(h) for h in result["horizons"]] == ["7", "14", "30"]
        assert zones["14"] is None                       # ağırlık 0 → görüş yok → bölge yok
        assert result["confident"] == [True, False, True]
        for i, horizon in ((0, "7"), (2, "30")):
            zone = zones[horizon]
            # Çapa sunucunun `base_price`'ı; ATR fiyatın kesri (0.02 · 4500 = 90 $).
            assert zone["near"] == round(result["base_price"] * (1 + result["mean"][i]), 2) == 4511.25
            assert zone["band"] == round(result["base_price"] * result["error"][i], 2) == 180.0
            assert zone["atr"] == 90.0
            assert zone["stop"] < zone["buy"][0] < zone["entry"] < zone["buy"][1] < zone["near"] \
                < zone["sell"][0] < zone["sell"][1]
            assert zone["params_version"] == "scenario-v1"
            assert set(zone) == {"near", "band", "atr", "buy", "sell", "stop", "entry", "risk_per_unit",
                                 "params_version"}
        stale = client.post("/v1/predict", json={**body, "source_date": (today - timedelta(days=8)).isoformat()})
        unknown = client.post("/v1/predict", json={"price": 4500, "features": body["features"]})
        for reply, status in ((stale.json(), "STALE_DATA"), (unknown.json(), "INSUFFICIENT_DATA")):
            assert reply["status"] == status and reply["mean"] == result["mean"]
            assert reply["scenario_zones"] == {"7": None, "14": None, "30": None}
