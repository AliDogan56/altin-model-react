"""Chronological outer tests with separate, purged calibration windows."""
from dataclasses import dataclass
from datetime import date, timedelta
from bisect import bisect_left
import math

import numpy as np

EVALUATION_VERSION = "nested-purged-v1"


@dataclass(frozen=True)
class TemporalFold:
    train: np.ndarray
    calibration: np.ndarray
    test: np.ndarray


def target_dates_for_rows(rows: list[dict], labelled: list[int], horizon: int) -> list[date]:
    """Use explicit realized timestamps or the first available bar on/after t+h.

    A last labelled target without an observable endpoint is rejected, not guessed.
    """
    dates = [date.fromisoformat(row["date"]) for row in rows]
    positions = {day: i for i, day in enumerate(dates)}
    target_name = f"target_return_{horizon}d"
    for index, row in enumerate(rows):
        if (target_name in row and row[target_name] in (None, "")
                and bisect_left(dates, dates[index] + timedelta(days=horizon)) < len(dates)):
            raise ValueError(f"Missing matured {horizon}d target at {dates[index]}")
    result = []
    for index in labelled:
        earliest = dates[index] + timedelta(days=horizon)
        explicit = rows[index].get(f"target_date_{horizon}d")
        if explicit:
            endpoint = date.fromisoformat(explicit)
        else:
            target = bisect_left(dates, earliest)
            if target == len(dates):
                raise ValueError(f"{horizon}d labelled target has no observed endpoint at {dates[index]}")
            endpoint = dates[target]
        if endpoint < earliest or endpoint > dates[-1]:
            raise ValueError(f"Invalid {horizon}d target endpoint at {dates[index]}")
        if endpoint not in positions:
            raise ValueError(f"{horizon}d target endpoint is not an observed close at {dates[index]}")
        if target_name in rows[index]:
            expected = float(rows[positions[endpoint]]["xauusd_close"]) / float(rows[index]["xauusd_close"]) - 1
            if not math.isclose(float(rows[index][target_name]), expected, rel_tol=0, abs_tol=1e-10):
                raise ValueError(f"{horizon}d target does not match actual future close at {dates[index]}")
        result.append(endpoint)
    return result


def purged_walk_forward_splits(feature_dates: list[date], target_dates: list[date], *,
                               min_train: int = 100, min_calibration: int = 30,
                               ratios=(0.55, 0.70, 0.85)) -> list[TemporalFold]:
    if len(feature_dates) != len(target_dates):
        raise ValueError("Feature and target timestamp counts differ")
    if any(left >= right for left, right in zip(feature_dates, feature_dates[1:])):
        raise ValueError("Feature dates must be unique and strictly chronological")
    if any(end <= start for start, end in zip(feature_dates, target_dates)):
        raise ValueError("Target endpoint must follow its feature timestamp")
    count = len(feature_dates)
    starts = [int(count * ratio) for ratio in ratios]
    folds = []
    for fold, start in enumerate(starts):
        end = starts[fold + 1] if fold + 1 < len(starts) else count
        if start >= count or end <= start:
            continue
        # Actual label maturity, not an assumed number of rows/trading days.
        eligible = [i for i in range(start) if target_dates[i] < feature_dates[start]]
        calibration_size = max(min_calibration, int(len(eligible) * 0.20))
        if len(eligible) <= calibration_size:
            continue
        calibration = eligible[-calibration_size:]
        train = [i for i in range(calibration[0]) if target_dates[i] < feature_dates[calibration[0]]]
        if len(train) < min_train:
            continue
        folds.append(TemporalFold(np.asarray(train), np.asarray(calibration), np.arange(start, end)))
    return folds
