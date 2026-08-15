import httpx
from fastapi.testclient import TestClient

from app.main import app


def test_missing_service_prefix_returns_standard_gateway_error():
    with TestClient(app) as client:
        response = client.get("/v1/market/spot")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "SERVICE_ROUTE_NOT_FOUND"
    assert body["service"] == "api-gateway"
    assert body["path"] == "/v1/market/spot"
    assert body["trace_id"] == response.headers["X-Trace-Id"]


def test_upstream_error_is_standardized_and_service_prefix_is_removed():
    seen_path = None

    def upstream(request: httpx.Request) -> httpx.Response:
        nonlocal seen_path
        seen_path = request.url.path
        return httpx.Response(502, json={"detail": "FRED kaynağı cevap vermedi"})

    with TestClient(app) as client:
        app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        response = client.get("/market-service/v1/market/fred?id=DGS10")
    body = response.json()
    assert seen_path == "/v1/market/fred"
    assert response.status_code == 502
    assert body["code"] == "UPSTREAM_ERROR"
    assert body["service"] == "market-service"
    assert body["message"] == "FRED kaynağı cevap vermedi"
    assert body["trace_id"] == response.headers["X-Trace-Id"]
