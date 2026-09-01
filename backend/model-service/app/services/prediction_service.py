from ..models.api_models import PredictIn
from .feature_service import frozen_now
from .model_service import model_service


class PredictionService:
    def predict(self, payload: PredictIn) -> dict:
        # Donmuş girdiler sunucuda belirlenir; istemciye bırakılırsa çağıran
        # bunu atlayıp tahmini sessizce eski davranışa döndürebilirdi.
        return model_service.predict(payload.features, payload.price, frozen_now())


prediction_service = PredictionService()
