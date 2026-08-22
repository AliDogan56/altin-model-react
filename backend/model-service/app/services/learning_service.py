from ..config import settings
from ..models.api_models import TrainIn
from .model_service import model_service
from .trainer import train_model


class LearningService:
    def metrics(self) -> dict:
        return {"environment": settings.environment, "active_model": model_service.version,
                "source": "XAU/USD", "horizons": model_service.horizons,
                "metrics": model_service.active.get("metrics", {}) if model_service.active else {}}

    def train(self, payload: TrainIn) -> dict:
        result = train_model(epochs=payload.epochs, minimum_rows=payload.minimum_rows)
        model_service.reload()
        return result


learning_service = LearningService()
