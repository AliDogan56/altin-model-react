from datetime import datetime, timedelta, timezone
import sqlite3
from ..config import settings
from ..models.api_models import PredictIn
from .feature_service import frozen_now, latest_features
from .model_service import model_service
from .prediction_ledger import PredictionLedger


class PredictionService:
    def predict(self, payload: PredictIn) -> dict:
        # Donmuş girdiler sunucuda belirlenir; istemciye bırakılırsa çağıran
        # bunu atlayıp tahmini sessizce eski davranışa döndürebilirdi.
        return self._forecast(payload, kind="client_scenario", provenance=None)

    def canonical(self) -> dict:
        latest = latest_features()
        provenance = latest.get("provenance", {})
        # Do not call a futures proxy or unverifiable current-vintage snapshot
        # an official daily XAU/USD forecast.
        if not (provenance.get("validated") and provenance.get("price_instrument") == "XAUUSD_spot"
                and provenance.get("availability") == "point_in_time"
                and provenance.get("macro_vintage") == "point_in_time"):
            raise ValueError("UNVERIFIED_PROVENANCE: official prediction is disabled for this dataset")
        return self._forecast(PredictIn(price=latest["price"], features=latest["features"],
                                       source_date=latest["date"]), kind="canonical_daily", provenance=provenance)

    def _forecast(self, payload: PredictIn, *, kind: str, provenance: dict | None) -> dict:
        now = datetime.now(timezone.utc)
        source_date = payload.source_date
        origin = source_date if kind == "canonical_daily" else now.date()
        if source_date and source_date > now.date():
            raise ValueError("Feature source date cannot be in the future")
        if kind == "canonical_daily" and (origin is None or any(
                origin + timedelta(days=h) <= now.date() for h in model_service.horizons)):
            raise ValueError("RETROACTIVE_FORECAST: canonical issuance must precede every target date")
        result = model_service.predict(payload.features, payload.price, frozen_now())
        result.update({"prediction_timestamp": now.isoformat(), "origin_date": origin.isoformat(),
                       "feature_source_date": payload.source_date.isoformat() if payload.source_date else None,
                       "forecast_kind": kind, "provenance": provenance,
                       "input_verification": "verified_canonical" if provenance else "unverified_client_scenario",
                       "target_dates": [(origin + timedelta(days=h)).isoformat() for h in result["horizons"]],
                       "target_date_rule": "first_verified_session_on_or_after_target_date",
                       "logging": {"enabled": getattr(settings, "prediction_logging", False), "recorded": False}})
        if source_date and (now.date() - source_date).days > 7:
            result["status"] = "STALE_DATA"
            result["confident"] = [False] * len(result["horizons"])
            result["no_view_reasons"] = [reasons + ["source_date_older_than_7_calendar_days"]
                                         for reasons in result["no_view_reasons"]]
        elif source_date is None:
            result["status"] = "INSUFFICIENT_DATA"
            result["confident"] = [False] * len(result["horizons"])
            result["no_view_reasons"] = [reasons + ["feature_source_date_unknown"]
                                         for reasons in result["no_view_reasons"]]
        if getattr(settings, "prediction_logging", False):
            try:
                ids = PredictionLedger(settings.prediction_log_path).append(
                    result, payload.features, kind=kind,
                    instrument=provenance["price_instrument"] if provenance else "client_unspecified")
                result["logging"].update({"recorded": True, "prediction_ids": ids})
            except (OSError, ValueError, sqlite3.Error) as error:
                result["logging"]["error"] = type(error).__name__
        return result


prediction_service = PredictionService()
