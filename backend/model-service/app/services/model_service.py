import json
from pathlib import Path

import numpy as np

from ..config import ROOT, settings

INITIAL_MODEL_PATH = ROOT / "data" / "initial_model.json"
BAND_SCALE = 0.81


class ModelService:
    def __init__(self):
        self.initial = json.loads(INITIAL_MODEL_PATH.read_text())
        self.active = None
        self.version = f"initial-{self.initial['latestDate']}"
        self.reload()

    @property
    def features(self):
        return self.active["features"] if self.active else self.initial["features"]

    @property
    def horizons(self):
        return self.active["horizons"] if self.active else self.initial["horizons"]

    def reload(self):
        pointer = settings.model_dir / "active.json"
        if pointer.exists():
            metadata = json.loads(pointer.read_text())
            artifact = Path(metadata["artifact_path"])
            if artifact.exists():
                import joblib
                self.active = joblib.load(artifact)
                self.version = metadata["version"]

    def _initial_predict(self, features: dict):
        x = np.array([(float(features[k]) - self.initial["xMean"][i]) / self.initial["xStd"][i] for i, k in enumerate(self.initial["features"])])
        x = np.clip(x, -6, 6)
        outputs = []
        for network in self.initial["models"]:
            a1 = np.maximum(0, x @ np.array(network["w1"]) + np.array(network["b1"]))
            a2 = np.maximum(0, a1 @ np.array(network["w2"]) + np.array(network["b2"]))
            raw = a2 @ np.array(network["w3"]) + np.array(network["b3"])
            outputs.append(raw * np.array(self.initial["yStd"]) + np.array(self.initial["yMean"]))
        outputs = np.array(outputs)
        mean = outputs.mean(axis=0)
        ensemble_error = outputs.std(axis=0) * 1.64
        error = np.maximum(np.array(self.initial["residual80"]), ensemble_error) * BAND_SCALE
        return mean, error

    def _trained_predict(self, features: dict):
        artifact = self.active
        x = np.array([float(features[k]) for k in artifact["features"]])
        x = np.clip((x - artifact["x_mean"]) / artifact["x_std"], -6, 6)
        scaled = artifact["network"].predict(x.reshape(1,-1))[0]
        mean = scaled * artifact["y_std"] + artifact["y_mean"]
        return mean, np.array(artifact["residual70"])

    def predict(self, features: dict, price: float):
        missing = [name for name in self.features if name not in features]
        if missing:
            raise ValueError(f"Eksik model girdileri: {', '.join(missing)}")
        mean, error = self._trained_predict(features) if self.active else self._initial_predict(features)
        return {"version": self.version, "horizons": self.horizons, "mean": mean.tolist(), "error": error.tolist(),
                "base_price": price, "prices": [price * (1 + value) for value in mean]}


model_service = ModelService()
