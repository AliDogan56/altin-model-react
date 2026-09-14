import pandas as pd

from app.services import forecast_ledger as ledger


def test_ledger_add_resolve_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(ledger, "FORECASTS", tmp_path / "forecasts.csv")
    monkeypatch.setattr(ledger, "OUTCOMES", tmp_path / "outcomes.csv")
    fid = ledger.add_forecast({"as_of_date": "2026-01-05", "base_price": 4000.0, "price_source": "LBMA_PM", "horizon_days": 30, "p10": 3700.0, "p50": 4050.0, "p90": 4400.0, "p_up": 0.6, "p_bull": 0.25, "p_base": 0.5, "p_bear": 0.25, "method_version": "test", "inputs_hash": "x", "note": ""})
    assert fid.startswith("20260105-30g-")
    spot = pd.Series([4100.0, 4120.0], index=pd.to_datetime(["2026-02-04", "2026-02-05"]))
    out = ledger.resolve(spot, pd.Timestamp("2026-02-10"))
    assert len(out) == 1 and out[0]["in_80"] is True and out[0]["direction_hit"] is True
    assert out[0]["actual_date"] == "2026-02-04"
    assert ledger.resolve(spot, pd.Timestamp("2026-02-10")) == []  # yalnız ekleme; ikinci kez çözümlenmez
    summary = ledger.summary()
    assert summary["cozumlenen"] == 1 and summary["ufuk_bazinda"]["30"]["kapsam_80"] == 1.0
