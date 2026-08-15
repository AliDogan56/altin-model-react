from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.neural_network import MLPRegressor

from ..config import settings
from ..repositories.gold_repository import gold_repository


def train_model(feature_names: list[str], horizons: list[int], epochs: int, minimum_rows: int):
    x_rows, y_rows = gold_repository.completed_training_rows(feature_names, horizons)
    if len(x_rows) < minimum_rows:
        raise ValueError(f"Yeniden eğitim için {minimum_rows} tamamlanmış örnek gerekli; şu anda {len(x_rows)} var")
    x, y = np.asarray(x_rows, dtype=np.float64), np.asarray(y_rows, dtype=np.float64)
    split = max(1, int(len(x) * .8))
    x_mean, x_std = x[:split].mean(0), x[:split].std(0)
    y_mean, y_std = y[:split].mean(0), y[:split].std(0)
    x_std[x_std < 1e-8] = 1
    y_std[y_std < 1e-8] = 1
    xs, ys = (x - x_mean) / x_std, (y - y_mean) / y_std
    network = MLPRegressor(hidden_layer_sizes=(28, 12), activation="relu", solver="adam", alpha=1e-4,
                           learning_rate_init=1e-3, max_iter=epochs, early_stopping=True,
                           validation_fraction=.15, n_iter_no_change=35, random_state=42)
    network.fit(xs[:split], ys[:split])
    validation_x = xs[split:] if split < len(x) else xs
    actual = y[split:] if split < len(x) else y
    prediction = network.predict(validation_x) * y_std + y_mean
    residual70 = np.quantile(np.abs(actual - prediction), .70, axis=0)
    metrics = {str(h): {"mae": float(mean_absolute_error(actual[:, i], prediction[:, i])),
                        "rmse": float(mean_squared_error(actual[:, i], prediction[:, i]) ** .5),
                        "direction": float(np.mean((actual[:, i] >= 0) == (prediction[:, i] >= 0)))} for i, h in enumerate(horizons)}
    version = datetime.now(timezone.utc).strftime("sklearn-mlp-%Y%m%dT%H%M%SZ")
    settings.model_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = settings.model_dir / f"{version}.joblib"
    joblib.dump({"network": network, "features": feature_names, "horizons": horizons, "x_mean": x_mean, "x_std": x_std,
                 "y_mean": y_mean, "y_std": y_std, "residual70": residual70}, artifact_path)
    metadata = {"version": version, "artifact_path": str(artifact_path), "metrics": metrics, "training_rows": len(x)}
    (settings.model_dir / "active.json").write_text(json.dumps(metadata, indent=2))
    gold_repository.register_model(version, datetime.now(timezone.utc).isoformat(), artifact_path, metrics, len(x))
    return metadata
