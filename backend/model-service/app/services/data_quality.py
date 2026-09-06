"""Fail-closed validation and lineage shared by dataset, training and serving."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from pathlib import Path
from typing import Mapping, Sequence

from .xau_dataset_service import FEATURES, HORIZONS


class DataQualityError(ValueError):
    pass


def finite_number(value, label: str, *, positive: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise DataQualityError(f"{label}: numeric value required") from error
    if not math.isfinite(number) or (positive and number <= 0):
        raise DataQualityError(f"{label}: finite{' positive' if positive else ''} value required")
    return number


def feature_vector(row: Mapping) -> tuple[float, ...]:
    """The canonical ordered 19-vector; used identically by trainer and API."""
    missing = [name for name in FEATURES if row.get(name) in (None, "")]
    if missing:
        raise DataQualityError(f"Missing feature / eksik girdi: {', '.join(missing)}")
    return tuple(finite_number(row[name], name) for name in FEATURES)


def _dates(values: Sequence, label: str) -> list[date]:
    parsed = []
    for value in values:
        try:
            day = value if type(value) is date else date.fromisoformat(value)
        except (TypeError, ValueError) as error:
            raise DataQualityError(f"{label}: invalid ISO date {value!r}") from error
        if parsed and day <= parsed[-1]:
            raise DataQualityError(f"{label}: duplicate or out-of-order date {day}")
        parsed.append(day)
    return parsed


def validate_bars(bars: Sequence) -> None:
    if not bars:
        raise DataQualityError("No price bars")
    _dates([bar.day for bar in bars], "price bars")
    for bar in bars:
        high = finite_number(bar.high, f"{bar.day} high", positive=True)
        low = finite_number(bar.low, f"{bar.day} low", positive=True)
        close = finite_number(bar.close, f"{bar.day} close", positive=True)
        if not low <= close <= high:
            raise DataQualityError(f"{bar.day}: OHLC requires low <= close <= high")


def validate_dataset_rows(rows: Sequence[Mapping], *, require_targets: bool = True) -> None:
    if not rows:
        raise DataQualityError("XAU/USD veri seti boş")
    _dates([row.get("date") for row in rows], "dataset")
    for row in rows:
        feature_vector(row)
        finite_number(row.get("xauusd_close"), f"{row['date']} close", positive=True)
        for horizon in HORIZONS:
            name = f"target_return_{horizon}d"
            if require_targets and name not in row:
                raise DataQualityError(f"Missing target column: {name}")
            value = row.get(name)
            if value in (None, ""):
                continue  # trailing, not-yet-mature labels are intentionally absent
            if finite_number(value, name) <= -1:
                raise DataQualityError(f"{name}: return must be greater than -1")


def dataset_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dataset_manifest_path(path: Path) -> Path:
    return Path(path).with_suffix(Path(path).suffix + ".manifest.json")


def load_dataset_manifest(path: Path, *, expected_hash: str | None = None) -> dict | None:
    manifest_path = dataset_manifest_path(path)
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DataQualityError("Dataset manifest cannot be read") from error
    if not isinstance(manifest, dict) or manifest.get("dataset_sha256") != (expected_hash or dataset_hash(path)):
        raise DataQualityError("Dataset manifest hash mismatch; snapshot is not verified")
    if manifest.get("features") != list(FEATURES):
        raise DataQualityError("Dataset manifest feature schema mismatch")
    return manifest


def unverified_provenance() -> dict:
    return {"availability": "unverified", "macro_vintage": "current_revision",
            "price_instrument": "unknown", "price_source": "unknown", "validated": False}


def assert_promotion_ready(path: Path) -> dict:
    """Diagnostic experiments may use legacy snapshots; promotion may not."""
    manifest = load_dataset_manifest(path)
    provenance = manifest.get("provenance", {}) if manifest else {}
    if not (provenance.get("validated") is True
            and provenance.get("availability") == "point_in_time"
            and provenance.get("macro_vintage") == "point_in_time"
            and provenance.get("price_instrument") == "XAUUSD_spot"):
        raise DataQualityError("Promotion blocked: verified point-in-time XAU/USD spot provenance required")
    return manifest
