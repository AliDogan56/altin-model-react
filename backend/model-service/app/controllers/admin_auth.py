"""Administrative mutations are disabled until an explicit bearer token exists."""
import secrets
from fastapi import Header, HTTPException
from ..config import settings


def require_admin(authorization: str | None = Header(default=None)) -> None:
    token = getattr(settings, "admin_token", "")
    if not token:
        raise HTTPException(503, "Administrative mutations are disabled; configure MODEL_ADMIN_TOKEN")
    expected = f"Bearer {token}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(401, "Administrative authentication required")
