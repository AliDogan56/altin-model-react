"""Sızıntısız zaman doğrulamasıyla bağımsız XAU/USD ufuk modelleri."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.neural_network import MLPRegressor

from ..config import ROOT, settings
from .xau_dataset_service import FEATURES, HORIZONS

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
    for stale in artifacts[max(1, keep):]:
        stale.with_suffix(".json").unlink(missing_ok=True)
        stale.unlink(missing_ok=True)


SEEDS = (17, 42, 91)


def _network(epochs: int, seed: int) -> MLPRegressor:
    # Veri hacmine göre küçük ve güçlü düzenlileştirilmiş ağ ezberleme riskini azaltır.
    return MLPRegressor(hidden_layer_sizes=(8, 4), activation="tanh", solver="lbfgs",
                        alpha=0.08, max_iter=epochs, random_state=seed)


def _fit_predict(x_train, y_train, x_test, epochs: int):
    mean, std = x_train.mean(0), x_train.std(0)
    std[std < 1e-9] = 1.0
    scaled_train, scaled_test = (x_train - mean) / std, (x_test - mean) / std
    models = [_network(epochs, seed).fit(scaled_train, y_train) for seed in SEEDS]
    prediction = np.mean([model.predict(scaled_test) for model in models], axis=0)
    return prediction, models, mean, std


def _walk_forward(x: np.ndarray, y: np.ndarray, horizon: int, epochs: int):
    """Genişleyen pencere; kat sınırında hedef örtüşmesini purge eder."""
    count = len(x)
    starts = [int(count * ratio) for ratio in (0.55, 0.70, 0.85)]
    predictions = np.full(count, np.nan)
    for fold, start in enumerate(starts):
        end = starts[fold + 1] if fold + 1 < len(starts) else count
        train_end = start - horizon
        if train_end < 100:
            continue
        predictions[start:end], _, _, _ = _fit_predict(x[:train_end], y[:train_end], x[start:end], epochs)
    mask = np.isfinite(predictions)
    return y[mask], predictions[mask]


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
    x = np.asarray([[float(row[name]) for name in FEATURES] for row in rows], dtype=np.float64)
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


def train_model(epochs: int = 600, minimum_rows: int = 300,
                dataset_path: Path = DATASET_PATH, artifact_path: Path | None = None):
    rows, all_x = _load_dataset(dataset_path)
    per_horizon, metrics, training_rows_by_horizon = {}, {}, {}
    for horizon in HORIZONS:
        target_name = f"target_return_{horizon}d"
        labelled = [i for i, row in enumerate(rows) if row.get(target_name, "") != ""]
        if len(labelled) < minimum_rows:
            raise ValueError(f"{horizon} günlük XAU/USD eğitimi için en az {minimum_rows} etiketli satır gerekli; {len(labelled)} bulundu")
        x = all_x[labelled]
        targets = np.asarray([float(rows[i][target_name]) for i in labelled])
        training_rows_by_horizon[str(horizon)] = len(labelled)
        actual, oof = _walk_forward(x, targets, horizon, epochs)
        if len(actual) < 100:
            raise ValueError(f"{horizon} günlük ufuk için yeterli katman dışı tahmin üretilemedi")
        baseline_mse = float(np.mean(actual ** 2))
        mse = float(np.mean((actual - oof) ** 2))
        weight, skill = _weight_and_skill(actual, oof)
        weighted_oof = weight * oof
        weighted_mse = float(np.mean((actual - weighted_oof) ** 2))
        latest, networks, x_mean, x_std = _fit_predict(x, targets, all_x[-1:], epochs)
        residual = np.abs(actual - weighted_oof)
        per_horizon[horizon] = {"networks": networks, "x_mean": x_mean, "x_std": x_std,
                                "weight": weight,
                                "error80": float(np.quantile(residual, 0.80)),
                                "training_volatility": float(np.median(x[:, FEATURES.index("gold_volatility_20d")]))}
        metrics[str(horizon)] = {
            "mae": float(mean_absolute_error(actual, weighted_oof)),
            "rmse": float(mean_squared_error(actual, weighted_oof) ** 0.5),
            "direction": None if weight == 0 else float(np.mean((actual >= 0) == (weighted_oof >= 0))),
            "zero_baseline_rmse": baseline_mse ** 0.5,
            "raw_skill_vs_zero": 0.0 if baseline_mse == 0 else 1 - mse / baseline_mse,
            "skill_vs_zero": skill,
            "weight": weight, "active": weight > 0,
            "within_2pp": float(np.mean(residual <= 0.02)),
            "error80": float(np.quantile(residual, 0.80)),
            "oof_rows": int(len(actual)), "latest_fit_return": float(weight * latest[0]),
        }
    version = datetime.now(timezone.utc).strftime("xauusd-mlp-%Y%m%dT%H%M%SZ")
    artifact = {"version": version, "source": "XAU/USD", "features": list(FEATURES),
                "horizons": list(HORIZONS), "per_horizon": per_horizon,
                "training_rows": training_rows_by_horizon[_primary_horizon_key(training_rows_by_horizon)],
                "training_rows_by_horizon": training_rows_by_horizon,
                "dataset_rows": len(rows), "training_start": rows[0]["date"],
                "training_end": {str(h): rows[max(i for i, row in enumerate(rows)
                    if row.get(f'target_return_{h}d', '') != '')]["date"] for h in HORIZONS},
                "latest_features": {name: float(rows[-1][name]) for name in FEATURES},
                "latest_price": float(rows[-1]["xauusd_close"]), "metrics": metrics}
    # Varsayılan hedef MODEL_DIR: Docker'da kalıcı volume. Önceden imajın içindeki
    # data/ klasörüne yazılıyordu; her container yeniden başlatıldığında yeniden
    # eğitilen model kayboluyor, volume ise hiç kullanılmıyordu.
    explicit = artifact_path is not None
    model_dir = Path(artifact_path).parent if explicit else Path(settings.model_dir)
    target = Path(artifact_path) if explicit else model_dir / f"{version}.joblib"
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, target)

    metadata = {key: artifact[key] for key in ("version", "source", "training_rows", "training_rows_by_horizon",
                                                "training_start", "training_end", "metrics")}
    metadata["artifact_path"] = str(target)
    target.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    if not explicit:
        # Servis bu işaretçiden okur; imaj build'i volume'a pointer bırakmamalı.
        (model_dir / "active.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        _prune(model_dir, settings.keep_artifacts)
    return metadata
