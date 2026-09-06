"""Opt-in append-only records. Client scenarios never enter official metrics.

No scheduler, downloads, database initialization or writes occur on import/read.
Outcomes must be supplied explicitly from the same verified instrument; no
reconstruction of old forecasts from today's model or today's feature vector.
"""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

import numpy as np


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class PredictionLedger:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _writer(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript("""
          CREATE TABLE IF NOT EXISTS forecasts (
            id TEXT PRIMARY KEY, issued_at TEXT NOT NULL, origin_date TEXT NOT NULL,
            target_date TEXT NOT NULL, horizon INTEGER NOT NULL, kind TEXT NOT NULL,
            instrument TEXT NOT NULL, model_version TEXT NOT NULL, feature_hash TEXT NOT NULL,
            body TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS outcomes (
            prediction_id TEXT PRIMARY KEY REFERENCES forecasts(id), recorded_at TEXT NOT NULL,
            actual_date TEXT NOT NULL, actual_price REAL NOT NULL, source TEXT NOT NULL,
            body TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS forecast_monitoring_idx ON forecasts(kind,horizon,origin_date DESC);
          CREATE TRIGGER IF NOT EXISTS forecasts_no_update BEFORE UPDATE ON forecasts
            BEGIN SELECT RAISE(ABORT, 'forecasts are immutable'); END;
          CREATE TRIGGER IF NOT EXISTS forecasts_no_delete BEFORE DELETE ON forecasts
            BEGIN SELECT RAISE(ABORT, 'forecasts are immutable'); END;
          CREATE TRIGGER IF NOT EXISTS outcomes_no_update BEFORE UPDATE ON outcomes
            BEGIN SELECT RAISE(ABORT, 'outcomes are immutable'); END;
          CREATE TRIGGER IF NOT EXISTS outcomes_no_delete BEFORE DELETE ON outcomes
            BEGIN SELECT RAISE(ABORT, 'outcomes are immutable'); END;
        """)
        return connection

    def _reader(self):
        return sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True, timeout=10)

    def append(self, result: dict, features: dict, *, kind: str, instrument: str) -> list[str]:
        if kind not in {"client_scenario", "canonical_daily"}:
            raise ValueError("Unknown forecast kind")
        origin = date.fromisoformat(result["origin_date"])
        issued = datetime.fromisoformat(result["prediction_timestamp"])
        if issued.tzinfo is None:
            raise ValueError("Forecast issuance timestamp must be timezone-aware")
        issued = issued.astimezone(timezone.utc)
        if kind == "canonical_daily" and any(origin + timedelta(days=h) <= issued.date() for h in result["horizons"]):
            raise ValueError("Canonical forecasts must be issued before every target date")
        ids = []
        with self._writer() as db:
            for i, horizon in enumerate(result["horizons"]):
                # Canonical forecasts are deduplicated for a snapshot/model, so
                # repeated calls cannot inflate the daily observation count.
                identity = {"date": origin.isoformat(), "horizon": horizon,
                            "model": result["version"], "feature_hash": digest(features),
                            "price": result["base_price"], "instrument": instrument}
                ident = digest(identity) if kind == "canonical_daily" else uuid4().hex
                target = (origin + timedelta(days=horizon)).isoformat()
                price, mean, error = result["base_price"], result["mean"][i], result["error"][i]
                body = {**identity, "spot_price": price, "predicted_return": mean,
                        "predicted_price": price * (1 + mean), "lower_bound": price * (1 + mean - error),
                        "upper_bound": price * (1 + mean + error), "model_weight": result["weights"][i],
                        "has_view": result["confident"][i], "feature_vector": features,
                        "interval": result["intervals"][i], "status": result["status"],
                        "model_disagreement": result["model_disagreement"][i],
                        "feature_z_scores": result["ood"]["per_horizon"][i]["feature_z_scores"],
                        "provenance": result.get("provenance"), "input_policy": result.get("input_policy"),
                        "target_rule": "first_verified_session_on_or_after_target_date"}
                db.execute("INSERT OR IGNORE INTO forecasts VALUES(?,?,?,?,?,?,?,?,?,?)", (
                    ident, issued.isoformat(), origin.isoformat(), target, horizon, kind,
                    instrument, result["version"], digest(features), json.dumps(body, allow_nan=False)))
                ids.append(ident)
        return ids

    def reconcile(self, prediction_id: str, *, actual_date: str, actual_price: float,
                  instrument: str, source: str, first_session_verified: bool,
                  observed_at: str) -> None:
        if not first_session_verified or not source.strip() or not np.isfinite(actual_price) or actual_price <= 0:
            raise ValueError("Verified first-session observation and positive finite price required")
        observed = datetime.fromisoformat(observed_at)
        actual_day = date.fromisoformat(actual_date)
        if observed.tzinfo is None or observed > datetime.now(timezone.utc):
            raise ValueError("Observation timestamp must be timezone-aware and not future")
        if actual_day > observed.date():
            raise ValueError("Outcome has not yet been observed")
        if not self.path.exists():
            raise ValueError("Prediction ledger does not exist")
        with self._writer() as db:
            row = db.execute("SELECT instrument,target_date,body,issued_at,kind FROM forecasts WHERE id=?", (prediction_id,)).fetchone()
            if row is None or row[0] != instrument or actual_day < date.fromisoformat(row[1]):
                raise ValueError("Prediction/instrument/target mismatch")
            if observed <= datetime.fromisoformat(row[3]):
                raise ValueError("Outcome observation must follow forecast issuance")
            forecast = json.loads(row[2])
            expected_source = (forecast.get("provenance") or {}).get("price_source")
            if row[4] == "canonical_daily" and expected_source not in (None, "", "unknown") and source != expected_source:
                raise ValueError("Canonical settlement source must match forecast provenance")
            actual_return = actual_price / forecast["spot_price"] - 1
            body = {"actual_return": actual_return, "return_error": forecast["predicted_return"] - actual_return,
                    "absolute_error": abs(forecast["predicted_price"] - actual_price),
                    "direction_correct": None if forecast["predicted_return"] == 0 or actual_return == 0 else
                    ((forecast["predicted_return"] > 0) == (actual_return > 0)),
                    "covered": forecast["lower_bound"] <= actual_price <= forecast["upper_bound"],
                    "instrument": instrument, "first_session_verified": True, "observed_at": observed_at}
            # Reconciliation is append-only; a correction is deliberately not an
            # UPDATE. Caller must investigate an existing/conflicting outcome.
            db.execute("INSERT INTO outcomes VALUES(?,?,?,?,?,?)", (
                prediction_id, datetime.now(timezone.utc).isoformat(), actual_day.isoformat(), actual_price, source,
                json.dumps(body, allow_nan=False)))

    def monitoring(self) -> dict:
        empty = {"scope": "canonical_daily_only", "windows": {}, "alerts": [],
                 "grouping": "instrument/model_version/horizon; first issuance per origin_date only",
                 "thresholds_calibrated": False, "note": "Diagnostics; no automatic model promotion or confidence adjustment"}
        if not self.path.exists():
            return {**empty, "status": "NO_LOGGED_PREDICTIONS"}
        with self._reader() as db:
            rows = db.execute("""WITH issuance AS (
                SELECT *,ROW_NUMBER() OVER(
                  PARTITION BY instrument,model_version,horizon,origin_date ORDER BY issued_at ASC,id ASC) AS issuance_rank
                FROM forecasts WHERE kind='canonical_daily'), recent AS (
                SELECT *,ROW_NUMBER() OVER(
                  PARTITION BY instrument,model_version,horizon ORDER BY origin_date DESC) AS rank
                FROM issuance WHERE issuance_rank=1)
                SELECT f.horizon,f.body,o.body,f.model_version,f.instrument FROM recent f
                LEFT JOIN outcomes o ON o.prediction_id=f.id WHERE f.rank<=180
                ORDER BY f.origin_date DESC,f.issued_at DESC""").fetchall()
        windows, alerts = {}, []
        for instrument, version, horizon in sorted({(row[4], row[3], row[0]) for row in rows}):
            subset = [(json.loads(row[1]), json.loads(row[2]) if row[2] else None, row[3])
                      for row in rows if (row[4], row[3], row[0]) == (instrument, version, horizon)]
            for size in (30, 90):
                recent = subset[:size]
                completed = [(f, o) for f, o, _ in recent if o is not None]
                directional = [o["direction_correct"] for f, o in completed if f["has_view"] and o["direction_correct"] is not None]
                errors = [o["return_error"] for _, o in completed]
                zero_errors = [abs(o["actual_return"]) for _, o in completed]
                means = [f["predicted_return"] for f, _, _ in recent]
                prior = [f["predicted_return"] for f, _, _ in subset[size:size * 2]]
                avg = lambda values: float(np.mean(values)) if values else None
                summary = {"predictions": len(recent), "resolved": len(completed),
                    "model_version": version, "instrument": instrument, "horizon": horizon,
                    "observation_unit": "first issuance per origin_date in this model/instrument group",
                    "mae_return": avg([abs(e) for e in errors]), "bias_return": avg(errors),
                    "mae_price": avg([o["absolute_error"] for _, o in completed]),
                    "direction_accuracy": avg(directional), "directional_observations": len(directional),
                    "interval_coverage": avg([o["covered"] for _, o in completed]),
                    "nominal_coverages": sorted({f["interval"]["nominal_coverage"] for f, _, _ in recent}),
                    "mean_disagreement": avg([f["model_disagreement"] for f, _, _ in recent]),
                    "mean_prediction": avg(means),
                    "prediction_drift_mean_delta": avg(means) - avg(prior) if len(prior) == size else None,
                    "feature_mean_training_z": {name: avg([f["feature_z_scores"][name] for f, _, _ in recent])
                                                for name in (recent[0][0]["feature_z_scores"] if recent else {})}}
                baseline = avg(zero_errors)
                summary["mae_skill_vs_zero"] = 1 - summary["mae_return"] / baseline if baseline else None
                if len(completed) >= 30 and summary["mae_skill_vs_zero"] is not None and summary["mae_skill_vs_zero"] < 0:
                    alerts.append({"instrument": instrument, "model_version": version, "horizon": horizon,
                                   "window": size, "code": "OBSERVED_MAE_WORSE_THAN_ZERO", "automatic_action": False})
                windows[f"{instrument}/{version}/{horizon}d/{size}"] = summary
        return {**empty, "status": "OK" if rows else "NO_OFFICIAL_PREDICTIONS", "windows": windows, "alerts": alerts}
