from ..config import settings
from ..models.api_models import TrainIn
from .model_service import model_service
from .trainer import train_model


class LearningService:
    def metrics(self) -> dict:
        artifact = model_service.active or {}
        return {"environment": settings.environment, "active_model": artifact.get("version", model_service.version),
                "source": "XAU/USD", "horizons": model_service.horizons,
                "evaluation_version": artifact.get("evaluation_version"),
                "metrics": artifact.get("metrics", {})}

    def train(self, payload: TrainIn) -> dict:
        # Candidate evaluation must not silently replace the production model.
        result = train_model(epochs=payload.epochs, minimum_rows=payload.minimum_rows, promote=False)
        return result


learning_service = LearningService()
