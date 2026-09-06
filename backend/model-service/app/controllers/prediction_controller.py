from fastapi import APIRouter, HTTPException, Depends

from ..models.api_models import PredictIn
from ..services.feature_service import latest_features
from ..services.prediction_service import prediction_service
from ..services.model_service import model_service
from ..services.prediction_ledger import PredictionLedger
from ..config import settings
from .admin_auth import require_admin

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
    if model_service.active is None:
        raise HTTPException(503, "MODEL_UNAVAILABLE")
    try:
        return prediction_service.predict(payload)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/forecasts/canonical", dependencies=[Depends(require_admin)])
def canonical_forecast() -> dict:
    if model_service.active is None:
        raise HTTPException(503, "MODEL_UNAVAILABLE")
    try:
        return prediction_service.canonical()
    except (OSError, ValueError) as error:
        raise HTTPException(409, str(error)) from error


@router.get("/monitoring")
def monitoring() -> dict:
    if not getattr(settings, "prediction_logging", False):
        return {"status": "DISABLED", "scope": "canonical_daily_only", "windows": {}}
    return PredictionLedger(settings.prediction_log_path).monitoring()
