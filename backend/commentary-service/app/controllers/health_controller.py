from fastapi import APIRouter, HTTPException

from ..config import settings
from ..services.commentary_store import commentary_store

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment, "service": "commentary-service"}


@router.get("/ready")
def ready() -> dict:
    """Yayımlanmış bir yorum varsa hazır; yoksa 503 (ilk üretim henüz bitmemiş olabilir)."""
    latest = commentary_store.latest()
    if latest is None:
        raise HTTPException(503, "COMMENTARY_UNAVAILABLE")
    return {"status": "ready", "version": latest["version"]}
