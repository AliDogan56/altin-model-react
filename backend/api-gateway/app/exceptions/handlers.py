import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .gateway_exceptions import GatewayException

logger = logging.getLogger("api-gateway.exceptions")


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", None) or request.headers.get("X-Trace-Id") or uuid4().hex


def _response(request: Request, status_code: int, code: str, message: str,
              service: str | None = None) -> JSONResponse:
    trace_id = _trace_id(request)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status_code,
        "code": code,
        "message": message,
        "path": request.url.path,
        "service": service or getattr(request.state, "target_service", None) or "api-gateway",
        "trace_id": trace_id,
    }
    return JSONResponse(status_code=status_code, content=payload, headers={"X-Trace-Id": trace_id})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(GatewayException)
    async def gateway_exception_handler(request: Request, error: GatewayException) -> JSONResponse:
        trace_id = _trace_id(request)
        logger.error("gateway_error trace_id=%s service=%s status=%s code=%s path=%s message=%s",
                     trace_id, error.service or "api-gateway", error.status_code, error.code,
                     request.url.path, error.message)
        return _response(request, error.status_code, error.code, error.message, error.service)

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, error: Exception) -> JSONResponse:
        trace_id = _trace_id(request)
        logger.exception("unexpected_gateway_error trace_id=%s path=%s", trace_id, request.url.path)
        return _response(request, 500, "INTERNAL_GATEWAY_ERROR", "API Gateway beklenmeyen bir hata üretti")
