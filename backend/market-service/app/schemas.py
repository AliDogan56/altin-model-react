"""Geriye dönük import uyumluluğu; yeni kod app.models paketini kullanır."""

from .models.api_models import PredictIn, SnapshotIn, TrainIn

__all__ = ["PredictIn", "SnapshotIn", "TrainIn"]
