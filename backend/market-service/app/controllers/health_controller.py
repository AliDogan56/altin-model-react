from fastapi import APIRouter

from ..config import settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment, "service": "market-service"}
