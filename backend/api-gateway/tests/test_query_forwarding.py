import httpx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _market_base_url() -> str:
    return next(route for route in settings.routes if route.name == "market-service").base_url


def test_query_string_is_forwarded_verbatim_to_upstream():
    """Teknik analiz ucu sorgu parametreleriyle çalışacak (pivot_method, pivot_period);
    gateway yol önekini soyarken sorgu dizesini olduğu gibi, aynı sırayla iletmeli."""
    seen_url = None

    def upstream(request: httpx.Request) -> httpx.Response:
        nonlocal seen_url
        seen_url = request.url
        return httpx.Response(200, json={"ok": True, "query": request.url.query.decode()})

    query = "pivot_method=camarilla&pivot_period=daily"
    with TestClient(app) as client:
        app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        response = client.get(f"/market-service/v1/market/xau/technical?{query}")

    assert seen_url is not None, "üst servise hiç istek gitmedi"
    assert str(seen_url) == f"{_market_base_url()}/v1/market/xau/technical?{query}"
    assert seen_url.path == "/v1/market/xau/technical"
    assert seen_url.query == query.encode()
    assert seen_url.params.get("pivot_method") == "camarilla"
    assert seen_url.params.get("pivot_period") == "daily"
    assert response.status_code == 200
    assert response.json() == {"ok": True, "query": query}
    assert response.headers["X-Gateway-Upstream"] == "market-service"


def test_path_without_query_gets_no_question_mark():
    seen_url = None

    def upstream(request: httpx.Request) -> httpx.Response:
        nonlocal seen_url
        seen_url = request.url
        return httpx.Response(200, json={"ok": True})

    with TestClient(app) as client:
        app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        response = client.get("/market-service/v1/market/xau/technical")

    assert response.status_code == 200
    assert str(seen_url) == f"{_market_base_url()}/v1/market/xau/technical"
    assert seen_url.query == b""
