from ..models.api_models import PredictIn
from .model_service import model_service


class PredictionService:
    def predict(self, payload: PredictIn) -> dict:
        return model_service.predict(payload.features, payload.price)


prediction_service = PredictionService()
