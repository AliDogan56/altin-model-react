from fastapi import APIRouter, HTTPException

from ..config import settings
from ..services.model_service import model_service

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment, "model_version": model_service.version}


@router.get("/ready")
def ready() -> dict:
    if model_service.active is None:
        raise HTTPException(503, "MODEL_UNAVAILABLE")
    return {"status": "OK", "model_version": model_service.version}
