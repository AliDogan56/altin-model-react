from app.main import app


def test_market_service_exposes_only_market_contract():
    paths = set(app.openapi()["paths"])
    assert {"/v1/market/xau", "/v1/market/fred", "/v1/market/news"} <= paths
    assert "/v1/market/binance" not in paths
    assert "/v1/market/spot" not in paths
    assert "/v1/predict" not in paths
