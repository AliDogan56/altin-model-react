from fastapi import APIRouter

from ..config import settings
from ..services.model_service import model_service

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment, "model_version": model_service.version}
