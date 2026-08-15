import httpx
import time
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .config import settings
from .database import initialize, log_request
from .exceptions import GatewayException, UpstreamResponseException, UpstreamUnavailableException, register_exception_handlers
from .services.router_service import router_service

HOP_BY_HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length"}


def create_app() -> FastAPI:
    app = FastAPI(title="Altın Model API Gateway", version="1.0.0")
    register_exception_handlers(app)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])

    @app.on_event("startup")
    async def startup() -> None:
        initialize()
        app.state.client = httpx.AsyncClient(timeout=300, follow_redirects=False)

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await app.state.client.aclose()

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "environment": settings.environment, "gateway": "api-gateway"}

    @app.get("/gateway/routes")
    async def routes() -> dict:
        return {"routes": router_service.describe(), "default": settings.default_service.name}

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def proxy(path: str, request: Request) -> Response:
        request.state.trace_id = request.headers.get("X-Trace-Id") or uuid4().hex
        request_path = f"/{path}"
        try:
            target = router_service.resolve(request_path)
        except KeyError as error:
            raise GatewayException(404, "SERVICE_ROUTE_NOT_FOUND", error.args[0], "api-gateway") from error
        upstream_path = router_service.upstream_path(request_path, target)
        request.state.target_service = target.name
        started_at = time.monotonic()
        url = f"{target.base_url}{upstream_path}"
        if request.url.query:
            url = f"{url}?{request.url.query}"
        headers = {key: value for key, value in request.headers.items() if key.lower() not in HOP_BY_HOP_HEADERS}
        headers["X-Gateway-Service"] = target.name
        headers["X-Trace-Id"] = request.state.trace_id
        headers["X-Forwarded-Host"] = request.headers.get("host", "")
        try:
            upstream = await app.state.client.request(request.method, url, headers=headers, content=await request.body())
        except httpx.HTTPError as error:
            log_request(request.method, request_path, target.name, 503, (time.monotonic() - started_at) * 1000)
            raise UpstreamUnavailableException(target.name, f"{target.name} kullanılamıyor: {error}") from error
        if upstream.status_code >= 400:
            log_request(request.method, request_path, target.name, upstream.status_code,
                        (time.monotonic() - started_at) * 1000)
            try:
                body = upstream.json()
                message = body.get("detail") or body.get("message") or str(body)
            except ValueError:
                message = upstream.text.strip() or f"{target.name} HTTP {upstream.status_code} döndürdü"
            raise UpstreamResponseException(upstream.status_code, target.name, message)
        response_headers = {key: value for key, value in upstream.headers.items() if key.lower() not in HOP_BY_HOP_HEADERS}
        response_headers["X-Gateway-Upstream"] = target.name
        response_headers["X-Trace-Id"] = request.state.trace_id
        log_request(request.method, request_path, target.name, upstream.status_code, (time.monotonic() - started_at) * 1000)
        return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)

    return app


app = create_app()
