from fastapi import APIRouter, HTTPException

from ..models.api_models import PredictIn, SnapshotIn
from ..services.prediction_service import prediction_service

router = APIRouter(tags=["prediction"])


@router.post("/predict")
def predict(payload: PredictIn) -> dict:
    try:
        return prediction_service.predict(payload)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/snapshots")
def snapshot(payload: SnapshotIn) -> dict:
    try:
        return prediction_service.save_snapshot(payload)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
