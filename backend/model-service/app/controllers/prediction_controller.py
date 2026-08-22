from fastapi import APIRouter, HTTPException

from ..models.api_models import PredictIn
from ..services.feature_service import latest_features
from ..services.prediction_service import prediction_service

router = APIRouter(tags=["prediction"])


@router.get("/features/latest")
def features() -> dict:
    """Tahmin girdilerinin tek kaynağı; eğitim setiyle birebir aynı formül."""
    try:
        return latest_features()
    except (OSError, ValueError) as error:
        raise HTTPException(503, str(error)) from error


@router.post("/predict")
def predict(payload: PredictIn) -> dict:
    try:
        return prediction_service.predict(payload)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
