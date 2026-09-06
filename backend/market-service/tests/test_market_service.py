from app.main import app


def test_market_service_exposes_only_market_contract():
    paths = set(app.openapi()["paths"])
    assert {"/v1/market/xau", "/v1/market/xau/intraday", "/v1/market/xau/momentum", "/v1/market/xau/technical",
            "/v1/market/fred", "/v1/market/news"} <= paths
    assert "/v1/market/binance" not in paths
    assert "/v1/market/spot" not in paths
    assert "/v1/predict" not in paths


def test_momentum_ucu_kaldirilmadi_isaretlendi():
    """Eski uç halefine işaret eder; istemciler geçene kadar kalır."""
    ops = app.openapi()["paths"]
    assert ops["/v1/market/xau/momentum"]["get"]["deprecated"] is True
    assert "deprecated" not in ops["/v1/market/xau/technical"]["get"]
