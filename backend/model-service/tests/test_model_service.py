from app.services.model_service import model_service


def test_initial_model_predicts_all_horizons():
    result = model_service.predict(model_service.initial["latest"], model_service.initial["latestPrice"])
    assert result["horizons"] == [7, 30, 90, 180]
    assert len(result["mean"]) == 4
    assert all(value > 0 for value in result["prices"])
