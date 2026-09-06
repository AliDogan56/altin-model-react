"""Sızıntısız zaman doğrulamasıyla bağımsız XAU/USD ufuk modelleri."""
import csv
import hashlib
import json
import os
import platform
import subprocess
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.neural_network import MLPRegressor

from ..config import ROOT, settings
from .xau_dataset_service import FEATURES, HORIZONS
from .preprocessing import PREPROCESSING_VERSION, fit_scaler, transform_features
from .temporal_validation import EVALUATION_VERSION, purged_walk_forward_splits, target_dates_for_rows
from .data_quality import feature_vector, validate_dataset_rows, load_dataset_manifest

DATASET_PATH = ROOT / "data" / "xauusd_training_5y.csv"
# İsteğe bağlı yedek. Build sırasında **artık üretilmiyor** (imaj her kurulduğunda
# modeli değiştiriyordu); dosya normalde yoktur. Yol korunuyor ki elle bir artefakt
# gömmek gerekirse yükleme sırası çalışsın.
BUNDLED_ARTIFACT_PATH = ROOT / "data" / "xauusd_model.joblib"


def _prune(model_dir: Path, keep: int) -> None:
    """Saatlik eğitim artefaktları volume'da sınırsız birikmesin.

    Her artefaktın yanında aynı adlı `.json` özeti durur; ikisi birlikte silinmezse
    volume'da yetim metadata dosyaları kalır.
    """
    artifacts = sorted(model_dir.glob("*.joblib"), key=lambda path: path.stat().st_mtime, reverse=True)
    # A candidate must never delete the currently deployed champion.
    protected = None
    try:
        protected = Path(json.loads((model_dir / "active.json").read_text())["artifact_path"]).resolve()
    except (OSError, ValueError, KeyError):
        pass
    for stale in artifacts[max(1, keep):]:
        if protected is not None and stale.resolve() == protected:
            continue
        stale.with_suffix(".json").unlink(missing_ok=True)
        stale.unlink(missing_ok=True)


SEEDS = (17, 42, 91)


def _network(epochs: int, seed: int) -> MLPRegressor:
    # Veri hacmine göre küçük ve güçlü düzenlileştirilmiş ağ ezberleme riskini azaltır.
    return MLPRegressor(hidden_layer_sizes=(8, 4), activation="tanh", solver="lbfgs",
                        alpha=0.08, max_iter=epochs, random_state=seed)


def _fit_predict(x_train, y_train, x_test, epochs: int):
    mean, std = fit_scaler(x_train)
    scaled_train = transform_features(x_train, mean, std)
    scaled_test = transform_features(x_test, mean, std)
    models = [_network(epochs, seed).fit(scaled_train, y_train) for seed in SEEDS]
    prediction = np.mean([model.predict(scaled_test) for model in models], axis=0)
    return prediction, models, mean, std


def _volatility_scale(x: np.ndarray, reference: float) -> np.ndarray:
    return np.clip(x[:, FEATURES.index("gold_volatility_20d")] / max(reference, 1e-9), .75, 2.0)


def _metric_summary(actual: np.ndarray, prediction: np.ndarray, weights: np.ndarray) -> dict:
    residual = actual - prediction
    baseline_mae = float(np.mean(np.abs(actual)))
    baseline_mse = float(np.mean(actual ** 2))
    active = weights >= 0.2
    directional = active & (np.abs(actual) > 1e-12) & (np.abs(prediction) > 1e-12)
    return {
        "mae": float(np.mean(np.abs(residual))),
        "rmse": float(np.sqrt(np.mean(residual ** 2))),
        "median_absolute_error": float(np.median(np.abs(residual))),
        "bias": float(np.mean(prediction - actual)),
        "direction": (float(np.mean((actual[directional] > 0) == (prediction[directional] > 0)))
                      if directional.any() else None),
        "direction_definition": "Only weight >= 0.2 and nonzero actual/predicted returns; abstentions excluded",
        "directional_rows": int(directional.sum()),
        "active_fraction": float(np.mean(active)),
        "zero_baseline_mae": baseline_mae,
        "zero_baseline_rmse": baseline_mse ** .5,
        "mae_skill_vs_zero": None if baseline_mae == 0 else 1 - float(np.mean(np.abs(residual))) / baseline_mae,
        # Preserve legacy name as MSE skill, explicitly identify its definition.
        "skill_vs_zero": None if baseline_mse == 0 else 1 - float(np.mean(residual ** 2)) / baseline_mse,
        "skill_definition": "1 - MSE_model / MSE_zero_return",
        "within_2pp": float(np.mean(np.abs(residual) <= .02)),
        "oof_rows": int(len(actual)),
    }


def _walk_forward(x: np.ndarray, y: np.ndarray, horizon: int, epochs: int,
                  feature_dates: list[date], target_dates: list[date]):
    """Base fit -> purged weight calibration -> purged interval calibration -> outer test.

    Neither the outer test targets nor later folds choose an earlier fold's
    weight, activity or interval. Final future calibration is handled separately.
    """
    raw_oof = np.full(len(x), np.nan)
    served_oof = np.full(len(x), np.nan)
    weight_oof = np.full(len(x), np.nan)
    widths = {coverage: np.full(len(x), np.nan) for coverage in (.5, .7, .8, .9)}
    folds = []
    for fold in purged_walk_forward_splits(feature_dates, target_dates):
        boundary = max(1, int(len(fold.calibration) * .60))
        interval = fold.calibration[boundary:]
        weight_cal = np.asarray([i for i in fold.calibration[:boundary]
                                 if target_dates[i] < feature_dates[int(interval[0])]])
        if len(weight_cal) < 10 or len(interval) < 10:
            continue
        evaluation = np.concatenate((weight_cal, interval, fold.test))
        predicted, _, _, _ = _fit_predict(x[fold.train], y[fold.train], x[evaluation], epochs)
        weight_pred, interval_pred, test_pred = np.split(predicted, [len(weight_cal), len(weight_cal) + len(interval)])
        weight, _ = _weight_and_skill(y[weight_cal], weight_pred)
        reference = float(np.median(x[fold.train, FEATURES.index("gold_volatility_20d")]))
        normalized_error = np.abs(y[interval] - weight * interval_pred) / _volatility_scale(x[interval], reference)
        raw_oof[fold.test], served_oof[fold.test], weight_oof[fold.test] = test_pred, weight * test_pred, weight
        coverage_metrics = {}
        for coverage, output in widths.items():
            output[fold.test] = float(np.quantile(normalized_error, coverage)) * _volatility_scale(x[fold.test], reference)
            coverage_metrics[str(coverage)] = float(np.mean(np.abs(y[fold.test] - weight * test_pred) <= output[fold.test]))
        describe = lambda indices: {"start": feature_dates[int(indices[0])].isoformat(),
                                    "end": feature_dates[int(indices[-1])].isoformat(),
                                    "last_target": max(target_dates[int(i)] for i in indices).isoformat(),
                                    "rows": len(indices)}
        folds.append({"train": describe(fold.train), "weight_calibration": describe(weight_cal),
                      "interval_calibration": describe(interval), "test": describe(fold.test),
                      "weight": weight, "metrics": _metric_summary(y[fold.test], weight * test_pred,
                                                                    np.full(len(fold.test), weight)),
                      "empirical_coverage": coverage_metrics})
    mask = np.isfinite(raw_oof)
    if int(mask.sum()) < 100:
        raise ValueError(f"{horizon}d requires at least 100 independently tested observations")
    actual, raw, served, weights = y[mask], raw_oof[mask], served_oof[mask], weight_oof[mask]
    metrics = _metric_summary(actual, served, weights)
    metrics["raw_skill_vs_zero"] = 1 - float(np.mean((actual - raw) ** 2)) / max(float(np.mean(actual ** 2)), 1e-18)
    metrics["empirical_coverage"] = {str(c): float(np.mean(np.abs(actual - served) <= output[mask]))
                                     for c, output in widths.items()}
    records = [{"date": feature_dates[i].isoformat(), "target_date": target_dates[i].isoformat(),
                "actual": float(y[i]), "raw_return": float(raw_oof[i]),
                "served_return": float(served_oof[i]), "weight": float(weight_oof[i]),
                "interval_widths": {str(c): float(output[i]) for c, output in widths.items()}}
               for i in np.flatnonzero(mask)]
    return actual, raw, x[mask], metrics, {"folds": folds, "predictions": records}


def _load_dataset(path: Path):
    with path.open(encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise ValueError(f"XAU/USD veri seti boş: {path}")
    # Eski şemalı bir CSV ile eğitim, sütun adını söylemeyen KeyError veriyordu;
    # imaj build'i bu yüzden anlaşılmaz biçimde kırılabiliyordu.
    missing = [name for name in FEATURES if name not in rows[0]]
    if missing:
        raise ValueError(f"Veri setinde eksik sütun ({path}): {', '.join(missing)}")
    validate_dataset_rows(rows)
    x = np.asarray([feature_vector(row) for row in rows], dtype=np.float64)
    return rows, x


def _shrinkage_weight(actual: np.ndarray, oof: np.ndarray) -> float:
    """Katman dışı tahminin regresyon eğimi, [0, 1] aralığına kırpılmış.

    Önceden `np.cov` (ddof=1) ile `np.var` (ddof=0) bölünüyordu; ağırlık
    n/(n-1) kadar şişiyordu. Merkezlenmiş toplamlarla ddof belirsizliği kalmaz.
    """
    centered_oof = oof - oof.mean()
    denominator = float(np.sum(centered_oof ** 2))
    if denominator < 1e-18:
        return 0.0
    slope = float(np.sum((actual - actual.mean()) * centered_oof) / denominator)
    return float(np.clip(slope, 0.0, 1.0))


def _weight_and_skill(actual: np.ndarray, oof: np.ndarray) -> tuple[float, float]:
    """Ağırlık ve o ağırlıkla servis edilen tahminin sıfır-getiri bazına becerisi.

    Ağırlığı sıfırlama kararı ham beceriye, rapor ise ağırlıklı beceriye
    bakıyordu; bir ufuk "aktif" görünüp servis ettiği tahminle sıfırın altında
    kalabiliyordu. Karar artık fiilen servis edilen tahmin üzerinden verilir.
    """
    baseline_mse = float(np.mean(actual ** 2))
    if baseline_mse == 0:
        return 0.0, 0.0
    weight = _shrinkage_weight(actual, oof)
    skill = 1 - float(np.mean((actual - weight * oof) ** 2)) / baseline_mse
    if skill <= 0:
        return 0.0, 0.0
    return weight, skill


def _primary_horizon_key(rows_by_horizon: dict, horizons=HORIZONS) -> str:
    """`training_rows` alanı ilk ufuktan gelir; anahtar sabit "7" yazılıydı."""
    return str(horizons[0])


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       stderr=subprocess.DEVNULL, text=True, timeout=3).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _training_code_hash() -> str:
    digest = hashlib.sha256()
    for name in ("trainer.py", "preprocessing.py", "temporal_validation.py", "data_quality.py", "xau_dataset_service.py"):
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def train_model(epochs: int = 600, minimum_rows: int = 300,
                dataset_path: Path = DATASET_PATH, artifact_path: Path | None = None,
                promote: bool = False):
    """Train an isolated candidate; never silently replace the deployed champion.

    Promotion is deliberately a separate operator workflow after comparable OOS
    evidence and verified point-in-time provenance. Historical CSVs may be used
    for diagnostics but cannot be certified by their column names alone.
    """
    if promote:
        raise ValueError("Automatic promotion is disabled; review candidate/champion evidence and verified provenance first")
    dataset_path = Path(dataset_path)
    started = datetime.now(timezone.utc)
    # Check both sides of loading: the hourly refresh must not change our snapshot.
    dataset_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    rows, all_x = _load_dataset(dataset_path)
    if hashlib.sha256(dataset_path.read_bytes()).hexdigest() != dataset_hash:
        raise ValueError("Dataset changed while loading; train from an immutable snapshot")
    provenance = load_dataset_manifest(dataset_path, expected_hash=dataset_hash)
    per_horizon, metrics, training_rows_by_horizon, validation, training_end, target_end = {}, {}, {}, {}, {}, {}
    for horizon in HORIZONS:
        target_name = f"target_return_{horizon}d"
        labelled = [i for i, row in enumerate(rows) if row.get(target_name, "") != ""]
        if len(labelled) < minimum_rows:
            raise ValueError(f"{horizon} günlük XAU/USD eğitimi için en az {minimum_rows} etiketli satır gerekli; {len(labelled)} bulundu")
        x = all_x[labelled]
        targets = np.asarray([float(rows[i][target_name]) for i in labelled])
        dates = [date.fromisoformat(rows[i]["date"]) for i in labelled]
        endpoints = target_dates_for_rows(rows, labelled, horizon)
        training_rows_by_horizon[str(horizon)] = len(labelled)
        training_end[str(horizon)], target_end[str(horizon)] = dates[-1].isoformat(), max(endpoints).isoformat()
        actual, raw_oof, oof_x, measured, detail = _walk_forward(x, targets, horizon, epochs, dates, endpoints)
        # All labels below are historical at the future deployment date. They may
        # calibrate the final fit but MUST NOT replace outer-test performance above.
        weight, _ = _weight_and_skill(actual, raw_oof)
        latest, networks, x_mean, x_std = _fit_predict(x, targets, all_x[-1:], epochs)
        reference = float(np.median(x[:, FEATURES.index("gold_volatility_20d")]))
        normalized_error = np.abs(actual - weight * raw_oof) / _volatility_scale(oof_x, reference)
        quantiles = {str(c): float(np.quantile(normalized_error, c)) for c in (.5, .7, .8, .9)}
        interval = {"nominal_coverage": .8, "calibration_method": "historical-walk-forward-volatility-normalized",
                    "quantiles": quantiles, "outer_test_coverage": measured["empirical_coverage"],
                    "empirical_coverage": None, "empirical_scope": "outer_test_procedure_only",
                    "evaluation_version": EVALUATION_VERSION,
                    "note": "Outer-test coverage evaluates the training procedure, not a guarantee for this future fit"}
        per_horizon[horizon] = {"networks": networks, "x_mean": x_mean, "x_std": x_std,
                               "weight": weight, "error80": quantiles["0.8"],
                               "training_volatility": reference, "interval_calibration": interval}
        metrics[str(horizon)] = {**measured, "weight": weight, "active": weight >= .2,
                                 "error80": quantiles["0.8"], "latest_fit_return": float(weight * latest[0]),
                                 "evaluation_version": EVALUATION_VERSION}
        validation[str(horizon)] = detail
    version = datetime.now(timezone.utc).strftime("xauusd-mlp-candidate-%Y%m%dT%H%M%S%fZ")
    finished = datetime.now(timezone.utc)
    artifact = {"version": version, "source": "XAU/USD", "features": list(FEATURES),
                "horizons": list(HORIZONS), "per_horizon": per_horizon,
                "preprocessing_version": PREPROCESSING_VERSION,
                "input_policy": "canonical-asof-no-neutralization-v1",
                "features_version": (provenance or {}).get("feature_version", "legacy-unverified-v1"),
                "evaluation_version": EVALUATION_VERSION,
                "dataset_hash": dataset_hash, "dataset_provenance": provenance,
                "git_commit": _git_commit(), "training_code_hash": _training_code_hash(), "random_seeds": list(SEEDS),
                "hyperparameters": _network(epochs, SEEDS[0]).get_params(),
                "dependencies": {"python": platform.python_version(), "numpy": np.__version__, "scikit_learn": sklearn.__version__},
                "training_started_at": started.isoformat(), "training_finished_at": finished.isoformat(),
                "training_seconds": (finished - started).total_seconds(),
                "training_rows": training_rows_by_horizon[_primary_horizon_key(training_rows_by_horizon)],
                "training_rows_by_horizon": training_rows_by_horizon,
                "dataset_rows": len(rows), "dataset_start": rows[0]["date"], "dataset_end": rows[-1]["date"],
                "training_start": rows[0]["date"], "training_end": training_end, "target_end": target_end,
                "latest_features": dict(zip(FEATURES, feature_vector(rows[-1]))),
                "latest_price": float(rows[-1]["xauusd_close"]), "metrics": metrics,
                "validation": validation, "candidate": True, "promoted": False,
                "promotion_status": "REVIEW_REQUIRED",
                "limitations": ["Unverified/revised source data is diagnostic only unless separately certified point-in-time",
                                "Existing champion performance is not directly comparable unless reevaluated on identical outer folds"]}
    explicit = artifact_path is not None
    model_dir = Path(artifact_path).parent if explicit else Path(settings.model_dir)
    target = Path(artifact_path) if explicit else model_dir / f"{version}.joblib"
    model_dir.mkdir(parents=True, exist_ok=True)
    # Explicit outputs must not overwrite any existing champion or result.
    if target.exists():
        raise ValueError(f"Refusing to overwrite an existing artifact: {target}")
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        joblib.dump(artifact, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    metadata = {key: value for key, value in artifact.items()
                if key not in {"per_horizon", "latest_features", "validation"}}
    metadata["artifact_path"] = str(target.resolve())
    _atomic_json(target.with_suffix(".json"), metadata)
    if not explicit:
        _atomic_json(model_dir / "last_candidate.json", metadata)
        _prune(model_dir, settings.keep_artifacts)
    return metadata
