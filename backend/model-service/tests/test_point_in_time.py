from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.data_quality import DataQualityError
from app.services.point_in_time import (MacroObservation, PointInTimeSeries,
                                       build_point_in_time_rows, macro_features_as_of)
from app.services.xau_dataset_service import FRED_IDS, XauBar


def at(day, hour=16):
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=timezone.utc)


def observation(day, released, value, vintage="initial"):
    return MacroObservation(date.fromisoformat(day), at(released), value, vintage)


def test_publication_date_not_observation_date_controls_access_and_revision():
    series = PointInTimeSeries([
        observation("2024-01-01", "2024-02-13", 310),
        observation("2024-01-01", "2025-02-12", 312, "annual-revision"),
    ])
    assert series.latest_available(at("2024-01-31")) is None
    assert series.latest_available(at("2024-02-13", 15)) is None
    assert series.latest_available(at("2024-02-13", 16)).value == 310
    assert series.latest_available(at("2025-02-11")).value == 310
    assert series.latest_available(at("2025-02-12")).value == 312


def macro_fixture():
    series = {name: PointInTimeSeries([observation("2022-01-01", "2022-02-01", 100)])
              for name in FRED_IDS}
    series["CPILFESL"] = PointInTimeSeries([
        observation("2023-02-01", "2023-03-14", 200),
        observation("2023-03-01", "2023-04-12", 250),
        observation("2024-02-01", "2024-03-12", 220),
        observation("2024-03-01", "2024-04-10", 300),
    ])
    return series


def test_cpi_yoy_uses_exact_reference_month_on_leap_year_month_end():
    series = macro_fixture()
    features = macro_features_as_of(series, at("2024-03-31"), date(2024, 3, 31))
    # February is the latest RELEASED reference month; compare February 2023,
    # not March 2023 or unreleased March 2024.
    assert features["core_cpi_yoy"] == pytest.approx(10)


def test_future_release_append_is_invariant_for_all_macro_features():
    series = macro_fixture()
    before = macro_features_as_of(series, at("2024-03-31"), date(2024, 3, 31))
    series = {name: PointInTimeSeries([*value.observations,
               observation("2024-03-01", "2024-05-01", 99999, "future-revision")])
              for name, value in series.items()}
    after = macro_features_as_of(series, at("2024-03-31"), date(2024, 3, 31))
    assert before == after


def test_missing_exact_prior_year_month_does_not_use_another_month():
    series = macro_fixture()
    series["CPILFESL"] = PointInTimeSeries([
        observation("2023-01-01", "2023-02-14", 200),
        observation("2024-02-01", "2024-03-12", 220),
    ])
    assert macro_features_as_of(series, at("2024-03-31"), date(2024, 3, 31)) is None


def test_timezone_and_duplicate_release_validation():
    with pytest.raises(DataQualityError, match="timezone"):
        MacroObservation(date(2024, 1, 1), datetime(2024, 2, 1), 10, "initial")
    row = observation("2024-01-01", "2024-02-01", 100)
    with pytest.raises(DataQualityError, match="duplicate"):
        PointInTimeSeries([row, row])


def test_offline_builder_requires_completed_price_bars():
    start = date(2024, 2, 1)
    bars = [XauBar(start + timedelta(days=i), 2100 + i, 2000 + i, 2050 + i) for i in range(65)]
    known = {bar.day: at(bar.day.isoformat(), 20) for bar in bars}
    predictions = {bar.day: at(bar.day.isoformat(), 21) for bar in bars}
    rows = build_point_in_time_rows(bars, macro_fixture(), prediction_times=predictions,
                                    price_available_at=known)
    assert len(rows) == 5
    known[bars[-1].day] = at(bars[-1].day.isoformat(), 22)
    with pytest.raises(DataQualityError, match="not available"):
        build_point_in_time_rows(bars, macro_fixture(), prediction_times=predictions,
                                 price_available_at=known)
