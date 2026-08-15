from fastapi import APIRouter, HTTPException

from ..models.api_models import TrainIn
from ..services.learning_service import learning_service
from ..services.automatic_learning_service import automatic_learning_service

router = APIRouter(tags=["learning"])


@router.get("/learning/metrics")
def learning_metrics() -> dict:
    return learning_service.metrics()


@router.post("/training/run")
def training(payload: TrainIn) -> dict:
    try:
        return learning_service.train(payload)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/learning/job")
def job_status() -> dict:
    return automatic_learning_service.status()
