"""Versioned, train-only preprocessing shared by candidate training and inference."""
import numpy as np

PREPROCESSING_VERSION = "standard-clip-v1"
CLIP_SIGMA = 6.0


def fit_scaler(x_train: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(x_train, dtype=np.float64)
    if values.ndim != 2 or not len(values) or not np.isfinite(values).all():
        raise ValueError("Scaler requires a non-empty finite training matrix")
    mean, std = values.mean(axis=0), values.std(axis=0)
    std[std < 1e-9] = 1.0
    return mean, std


def transform_features(x: np.ndarray, mean: np.ndarray, std: np.ndarray,
                       clip: float = CLIP_SIGMA) -> np.ndarray:
    values = np.asarray(x, dtype=np.float64)
    if not np.isfinite(values).all() or not np.isfinite(mean).all() or not np.isfinite(std).all():
        raise ValueError("Feature transform requires finite inputs and scaler")
    if values.shape[-1] != len(mean) or np.asarray(std).shape != np.asarray(mean).shape or np.any(std <= 0):
        raise ValueError("Feature/scaler shape or scale is invalid")
    return np.clip((values - mean) / std, -clip, clip)
