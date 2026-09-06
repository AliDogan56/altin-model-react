"""Model senaryosu bölgeleri.

İlk dört test `frontend/src/domain/tradeZones.test.ts`'in birebir portudur
(aynı girdiler, aynı beklentiler). Pozisyon büyüklüğü sunucuda hesaplanmaz;
o iki test `risk_per_unit` üzerinden istemcinin yaptığı bölmeyi tekrarlar.
Kalanlar sunucuya özgü kurallar: görüş yoksa `None`, sonlu olmayan girdi
`None`, ortam değişkeniyle sabit değişimi, sent yuvarlaması ve tarayıcı
çıktısıyla eşdeğerlik (fixture varsa).
"""

import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.config import ROOT
from app.services.scenario_service import (PARAMS, PARAMS_VERSION, ScenarioParams,
                                           params_from_env, scenario_zones)

FIXTURE = Path(__file__).parent / "fixtures" / "tradezones_expected_20260906.json"
NAN, INF = float("nan"), float("inf")


def zones(price=100, mean=.05, err=.06, atr=.01, confident=True, params=None):
    return scenario_zones(price, mean, err, atr, confident, params)


def numbers_in(zone: dict) -> list[float]:
    return [zone[key] for key in ("near", "band", "atr", "stop", "entry", "risk_per_unit")] + zone["buy"] + zone["sell"]


# --- tradeZones.test.ts portu -------------------------------------------------

def test_buy_zone_below_forecast_sell_zone_above():
    """'alım bölgesi tahminin altında, satış üstündedir'"""
    z = zones(atr=.01)
    assert z["near"] == pytest.approx(105, abs=1e-9)
    assert z["buy"][0] < z["buy"][1] < z["near"] < z["sell"][0] < z["sell"][1]


def test_stop_is_always_below_buy_zone():
    """'zarar kes daima alım bölgesinin altındadır'"""
    z = zones(atr=.03)
    assert z["stop"] < z["buy"][0]


def test_wider_volatility_moves_stop_away_and_shrinks_position():
    """'oynaklık büyüdükçe zarar kes uzaklaşır ve pozisyon küçülür'"""
    narrow, wide = zones(atr=.005), zones(atr=.05)
    assert wide["stop"] < narrow["stop"]
    budget = 10_000 * 1 / 100
    assert budget / wide["risk_per_unit"] < budget / narrow["risk_per_unit"]


def test_position_size_is_proportional_to_risk_budget():
    """'pozisyon büyüklüğü risk bütçesiyle orantılıdır' — bölme istemcide kalır."""
    z = zones(atr=.01)
    one = 10_000 * 1 / 100 / z["risk_per_unit"]
    two = 10_000 * 2 / 100 / z["risk_per_unit"]
    assert two == pytest.approx(one * 2, rel=1e-9)


# --- sunucuya özgü kurallar --------------------------------------------------

def test_exact_geometry_matches_tradezones_formula():
    # near 105, band 6, atr 1 → buy 105−4.32/105−2.28, sell 105+2.10/105+4.32,
    # stop 100.68−max(1.5, 1.08), entry (100.68+102.72)/2, risk max(1, 2.52)
    assert zones(price=100, mean=.05, err=.06, atr=.01) == {
        "near": 105.0, "band": 6.0, "atr": 1.0, "buy": [100.68, 102.72], "sell": [107.1, 109.32],
        "stop": 99.18, "entry": 101.7, "risk_per_unit": 2.52, "params_version": "scenario-v1"}


def test_default_constants_are_the_frontend_constants_and_frozen():
    assert PARAMS == ScenarioParams(buy_low=.72, buy_high=.38, sell_low=.35, sell_high=.72,
                                    stop_atr=1.5, stop_band=.18, min_risk=1.0)
    assert PARAMS_VERSION == "scenario-v1"
    with pytest.raises(FrozenInstanceError):
        PARAMS.buy_low = 0  # type: ignore[misc]


def test_risk_per_unit_has_a_one_dollar_floor():
    z = zones(price=100, mean=0, err=.001, atr=.001)
    assert z["entry"] - z["stop"] < 1
    assert z["risk_per_unit"] == 1.0


def test_no_view_yields_none_not_a_zero_zone():
    assert zones(confident=False) is None
    assert zones(confident=True) is not None


@pytest.mark.parametrize("field", ["price", "mean", "err", "atr"])
@pytest.mark.parametrize("bad", [NAN, INF, -INF, None, "1"])
def test_non_finite_or_non_numeric_input_yields_none(field, bad):
    assert zones(**{field: bad}) is None


@pytest.mark.parametrize("price", [0, -1, -4500.0])
def test_non_positive_price_yields_none(price):
    assert zones(price=price) is None


def test_env_override_changes_one_constant_and_only_its_geometry():
    params = params_from_env({"SCENARIO_BUY_LOW": "0.9", "SCENARIO_MIN_RISK": "0"})
    assert params == ScenarioParams(buy_low=.9, min_risk=0.0)
    assert params_from_env({}) == ScenarioParams()
    default, overridden = zones(), zones(params=params)
    assert overridden["buy"][0] == pytest.approx(105 - 6 * .9, abs=.005)
    assert overridden["buy"][1] == default["buy"][1]
    assert overridden["sell"] == default["sell"]


@pytest.mark.parametrize("raw", ["abc", "", "nan", "inf", "-0.1"])
def test_invalid_env_value_is_a_runtime_error_naming_the_variable(raw):
    with pytest.raises(RuntimeError, match="SCENARIO_STOP_ATR"):
        params_from_env({"SCENARIO_STOP_ATR": raw})


def _import_in_fresh_interpreter(extra_env: dict[str, str]) -> subprocess.CompletedProcess:
    env = {key: value for key, value in os.environ.items() if not key.startswith("SCENARIO_")}
    env.update({"PYTHONPATH": str(ROOT), **extra_env})
    return subprocess.run([sys.executable, "-c", "from app.services.scenario_service import PARAMS; print(PARAMS.stop_atr)"],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)


def test_env_is_read_at_import_and_invalid_value_stops_the_service():
    """Bozuk sabit yanlış geometriyle sessizce çalışmak yerine açılışta patlar."""
    ok = _import_in_fresh_interpreter({"SCENARIO_STOP_ATR": "2.5"})
    assert ok.returncode == 0, ok.stderr
    assert ok.stdout.strip() == "2.5"
    bad = _import_in_fresh_interpreter({"SCENARIO_STOP_ATR": "iki"})
    assert bad.returncode != 0
    assert "RuntimeError" in bad.stderr and "SCENARIO_STOP_ATR" in bad.stderr


def test_values_are_rounded_to_cents_and_ordering_survives_rounding():
    z = zones(price=4476.6, mean=.0123456789, err=.045678912, atr=.020342287)
    for value in numbers_in(z):
        assert value == round(value, 2)
    assert z["stop"] < z["buy"][0] < z["entry"] < z["buy"][1] < z["near"] < z["sell"][0] < z["sell"][1]
    assert z["atr"] == round(4476.6 * .020342287, 2)


# --- tarayıcı çıktısıyla eşdeğerlik ------------------------------------------

LIVE_FIXTURE = Path(__file__).parent / "fixtures" / "predict_live_20260906.json"
# Sunucu sente yuvarlar, tarayıcı yuvarlamaz: fark en çok yarım sent.
CENT = .005 + 1e-6
GEOMETRY = ("near", "band", "atr", "stop", "entry")


def _load(path: Path, what: str) -> dict:
    if not path.exists():
        pytest.skip(f"{what} yok: {path}; yalnız formül testleri koştu")
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_same_geometry(zone: dict, expected: dict, context) -> None:
    for key in GEOMETRY:
        assert zone[key] == pytest.approx(expected[key], abs=CENT), (key, context)
    for key in ("buy", "sell"):
        assert zone[key] == pytest.approx(list(expected[key]), abs=CENT), (key, context)


def test_parity_with_browser_tradezones_fixture():
    """`tradeZones(forecast, values.price, features.gold_atr14_pct, …)` çıktısıyla birebir.

    Eski istemci görüş olmayan ufukta da bölge hesaplıyor ama kartta göstermiyordu
    (`hasView: false`). Sunucu aynı geometriyi üretir; farkı, görüş yokken hesaplayıp
    saklamak yerine `None` demesidir. İkisi de burada sınanır.
    """
    fixture = _load(FIXTURE, "tarayıcı eşdeğerlik fixture'ı")
    inputs, expected_by_horizon = fixture["inputs"], fixture["zones"]
    assert set(expected_by_horizon) == {str(h) for h in inputs["horizons"]}
    for i, horizon in enumerate(inputs["horizons"]):
        expected = expected_by_horizon[str(horizon)]
        args = (inputs["price"], inputs["mean"][i], inputs["err"][i], inputs["atrPct"])
        # Geometri: aynı formül, aynı sabitler.
        _assert_same_geometry(scenario_zones(*args, True), expected, horizon)
        # Pozisyon bölmesi istemcide kalır; sunucunun birim riskiyle aynı sonucu verir.
        risk = scenario_zones(*args, True)["risk_per_unit"]
        assert inputs["capital"] * inputs["riskPct"] / 100 / risk == pytest.approx(expected["units"], rel=1e-4)
        # Politika: görüş yoksa bölge yok.
        served = scenario_zones(*args, inputs["confident"][i])
        assert (served is None) == (not expected["hasView"]), horizon
        assert expected["hasView"] == inputs["confident"][i]


def test_parity_from_raw_production_predict_response():
    """Üretim yanıtı + istek girdisi → sunucu bölgeleri, tarayıcının hesapladığıyla aynı.

    `_forecast` içindeki yolun birebir aynısı: çapa `response.base_price`,
    `mean[i]`/`error[i]` ve isteğin `gold_atr14_pct` kesri.
    """
    live = _load(LIVE_FIXTURE, "üretim predict kaydı")
    expected_by_horizon = _load(FIXTURE, "tarayıcı eşdeğerlik fixture'ı")["zones"]
    response, request = live["response"], live["request"]
    assert "scenario_zones" not in response          # kayıt bu değişiklikten önce alındı
    assert response["base_price"] == request["price"]
    for i, horizon in enumerate(response["horizons"]):
        zone = scenario_zones(response["base_price"], response["mean"][i], response["error"][i],
                              request["features"]["gold_atr14_pct"], True)
        _assert_same_geometry(zone, expected_by_horizon[str(horizon)], horizon)
        assert zone["atr"] == pytest.approx(request["price"] * request["features"]["gold_atr14_pct"], abs=CENT)
