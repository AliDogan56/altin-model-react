"""Yönetici uçları açık bir bearer token tanımlanana kadar kapalıdır (model-service ile aynı kalıp)."""
import secrets

from fastapi import Header, HTTPException

from ..config import settings


def require_admin(authorization: str | None = Header(default=None)) -> None:
    token = settings.admin_token
    if not token:
        raise HTTPException(503, "Administrative mutations are disabled; configure COMMENTARY_ADMIN_TOKEN")
    expected = f"Bearer {token}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(401, "Administrative authentication required")
