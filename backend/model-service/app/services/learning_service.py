from ..config import settings
from ..models.api_models import TrainIn
from ..repositories.gold_repository import gold_repository
from .model_service import model_service
from .trainer import train_model


class LearningService:
    def metrics(self) -> dict:
        return {**gold_repository.learning_metrics(), "environment": settings.environment, "active_model": model_service.version,
                "policy": {"bias_min_samples": 5, "band_min_samples": 20, "retrain_min_rows": 80}}

    def train(self, payload: TrainIn) -> dict:
        result = train_model(model_service.features, model_service.horizons, payload.epochs, payload.minimum_rows)
        model_service.reload()
        return result


learning_service = LearningService()
