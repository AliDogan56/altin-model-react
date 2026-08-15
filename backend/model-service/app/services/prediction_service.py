from datetime import datetime, timezone

from ..models.api_models import PredictIn, SnapshotIn
from ..repositories.gold_repository import gold_repository
from .model_service import model_service


class PredictionService:
    def predict(self, payload: PredictIn) -> dict:
        return model_service.predict(payload.features, payload.price)

    def save_snapshot(self, payload: SnapshotIn) -> dict:
        observed_at = payload.observed_at or datetime.now(timezone.utc)
        forecast = model_service.predict(payload.features, payload.model_price)
        created = gold_repository.save_prediction_snapshot(observed_at.date(), observed_at, payload.model_price, payload.display_price,
                                                           payload.source, payload.display_source, payload.features, forecast)
        return {"created": created, "trade_date": observed_at.date(), "basis_usd": payload.display_price - payload.model_price,
                "model_reference": payload.source, "display_reference": payload.display_source, "forecast": forecast}


prediction_service = PredictionService()
