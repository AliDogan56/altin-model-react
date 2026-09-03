from app.services.router_service import router_service


def test_routes_model_and_market_requests():
    model = router_service.resolve("/model-service/v1/predict")
    market = router_service.resolve("/market-service/v1/market/spot")
    assert model.name == "model-service"
    assert market.name == "market-service"
    assert router_service.upstream_path("/model-service/v1/predict", model) == "/v1/predict"
    assert router_service.upstream_path("/market-service/v1/market/spot", market) == "/v1/market/spot"


def test_route_requires_service_name():
    try:
        router_service.resolve("/v1/market/spot")
    except KeyError:
        return
    raise AssertionError("Servis adı olmayan rota reddedilmeliydi")


def test_zaman_asimi_yol_bazli():
    """Eğitim yolu uzun, diğer her şey kısa süre alır; önek eşleşmesi tam bölümle yapılır."""
    from app.config import settings
    assert router_service.timeout_for("/v1/training/run") == settings.slow_timeout
    assert router_service.timeout_for("/v1/training") == settings.slow_timeout
    assert router_service.timeout_for("/v1/trainingx") == settings.upstream_timeout
    assert router_service.timeout_for("/v1/predict") == settings.upstream_timeout
    assert settings.upstream_timeout < settings.slow_timeout
    assert settings.upstream_timeout <= 120
