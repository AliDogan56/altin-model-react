"""Offline, opt-in macro builder with explicit release/vintage timestamps.

No network fetcher and no assumed publication lag live here. A caller must
provide evidence-backed release timestamps, vintages and completed-bar times.
The legacy CSV is not silently relabelled or retroactively repaired.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Mapping, Sequence

from .data_quality import DataQualityError, finite_number, validate_bars, validate_dataset_rows
from .xau_dataset_service import FRED_IDS, HORIZONS, XauBar, _gold_features


def _aware(timestamp: datetime) -> datetime:
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise DataQualityError("A timezone-aware information-availability timestamp is required")
    return timestamp


@dataclass(frozen=True)
class MacroObservation:
    observation_date: date
    available_at: datetime
    value: float
    vintage: str

    def __post_init__(self):
        _aware(self.available_at)
        if type(self.observation_date) is not date or not self.vintage:
            raise DataQualityError("Observation date and explicit vintage identifier are required")
        if self.available_at.date() < self.observation_date:
            raise DataQualityError("Observed macro values cannot be published before their observation period")
        finite_number(self.value, "macro observation")


class PointInTimeSeries:
    def __init__(self, observations: Sequence[MacroObservation]):
        self.observations = tuple(observations)
        keys = [(row.observation_date, row.available_at) for row in observations]
        if len(keys) != len(set(keys)):
            raise DataQualityError("Ambiguous duplicate observation/release timestamp")

    def latest_available(self, prediction_time: datetime, observation_cutoff: date | None = None):
        _aware(prediction_time)
        cutoff = observation_cutoff or prediction_time.date()
        usable = [row for row in self.observations
                  if row.available_at <= prediction_time and row.observation_date <= cutoff]
        return max(usable, key=lambda row: (row.observation_date, row.available_at)) if usable else None

    def value(self, prediction_time: datetime, observation_cutoff: date) -> float | None:
        row = self.latest_available(prediction_time, observation_cutoff)
        return float(row.value) if row else None

    def exact_month(self, prediction_time: datetime, year: int, month: int) -> float | None:
        _aware(prediction_time)
        usable = [row for row in self.observations if row.available_at <= prediction_time
                  and row.observation_date.year == year and row.observation_date.month == month]
        row = max(usable, key=lambda row: row.available_at) if usable else None
        return float(row.value) if row else None


def macro_features_as_of(series: Mapping[str, PointInTimeSeries], prediction_time: datetime,
                         reference_day: date) -> dict[str, float] | None:
    """All revisions must be available by prediction_time, including lagged values.

    Non-CPI lookbacks preserve legacy calendar-day definitions. CPI is matched
    to exactly the same reference month one year earlier, not 365 days earlier.
    No future releases, revised-after-prediction values or back-fills are used.
    """
    _aware(prediction_time)
    if reference_day > prediction_time.date():
        raise DataQualityError("Feature reference day is after prediction time")
    missing = set(FRED_IDS) - series.keys()
    if missing:
        raise DataQualityError(f"Missing PIT macro series: {', '.join(sorted(missing))}")

    def value(name, days=0):
        return series[name].value(prediction_time, reference_day - timedelta(days=days))

    def change(name, days):
        current, old = value(name), value(name, days)
        return None if current is None or old is None else current - old

    def ratio(name, days):
        current, old = value(name), value(name, days)
        return None if current is None or old in (None, 0) else current / old - 1

    ten, two, real = value("DGS10"), value("DGS2"), value("DFII10")
    old_ten, old_real = value("DGS10", 20), value("DFII10", 20)
    cpi = series["CPILFESL"].latest_available(prediction_time, reference_day)
    cpi_old = (series["CPILFESL"].exact_month(prediction_time, cpi.observation_date.year - 1,
                                           cpi.observation_date.month) if cpi else None)
    features = {
        "real_yield_change_5d": change("DFII10", 5),
        "real_yield_change_20d": change("DFII10", 20),
        "dollar_return_5d": ratio("DTWEXBGS", 5),
        "dollar_return_20d": ratio("DTWEXBGS", 20),
        "breakeven_change_20d": None if None in (ten, real, old_ten, old_real)
            else (ten - real) - (old_ten - old_real),
        "yield_curve_10y_2y": None if ten is None or two is None else ten - two,
        "vix_level": value("VIXCLS"), "vix_change_5d": change("VIXCLS", 5),
        "core_cpi_yoy": None if cpi is None or cpi_old in (None, 0) else (cpi.value / cpi_old - 1) * 100,
        "oil_return_5d": ratio("DCOILWTICO", 5), "oil_return_20d": ratio("DCOILWTICO", 20),
    }
    if any(value is None for value in features.values()):
        return None
    return {name: finite_number(value, name) for name, value in features.items()}


def build_point_in_time_rows(
    bars: Sequence[XauBar], series: Mapping[str, PointInTimeSeries], *,
    prediction_times: Mapping[date, datetime], price_available_at: Mapping[date, datetime],
) -> list[dict]:
    """Build diagnostic rows without modifying any production dataset/artifact.

    Timestamp maps are deliberately mandatory. They must come from verified
    source metadata; a guessed EOD/lag is not proof of historical availability.
    """
    validate_bars(bars)
    days = [bar.day for bar in bars]
    rows = []
    for index, bar in enumerate(bars):
        if index < 60:
            continue
        if bar.day not in prediction_times:
            raise DataQualityError(f"Missing prediction timestamp for {bar.day}")
        at = _aware(prediction_times[bar.day])
        for prior in bars[max(0, index - 60):index + 1]:
            if prior.day not in price_available_at or _aware(price_available_at[prior.day]) > at:
                raise DataQualityError(f"Price bar {prior.day} was not available at prediction time")
        macro = macro_features_as_of(series, at, bar.day)
        if macro is None:
            continue  # never backwards-fill a not-yet-released macro value
        gold = _gold_features(list(bars), index)
        targets = {}
        for horizon in HORIZONS:
            target_index = bisect_right(days, bar.day + timedelta(days=horizon - 1))
            targets[f"target_return_{horizon}d"] = ("" if target_index >= len(bars)
                else bars[target_index].close / bar.close - 1)
        rows.append({"date": bar.day.isoformat(), "xauusd_close": bar.close,
                     **gold, **macro, **targets})
    if rows:
        validate_dataset_rows(rows)
    return rows
