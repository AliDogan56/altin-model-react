import json
from datetime import date, datetime
from pathlib import Path

from ..db import connect, init_db, metrics, save_snapshot, training_rows


class GoldRepository:
    def initialize(self) -> None:
        init_db()

    def save_prediction_snapshot(self, trade_date: date, observed_at: datetime, model_price: float, display_price: float,
                                 source: str, display_source: str, features: dict, forecast: dict) -> bool:
        return save_snapshot(trade_date, observed_at, model_price, display_price, source, display_source, features, forecast)

    def learning_metrics(self) -> dict:
        return metrics()

    def completed_training_rows(self, feature_names: list[str], horizons: list[int]) -> tuple[list, list]:
        return training_rows(feature_names, horizons)

    def register_model(self, version: str, created_at: str, artifact_path: Path, model_metrics: dict, row_count: int) -> None:
        with connect() as db:
            db.execute("UPDATE model_versions SET active=0")
            db.execute("INSERT INTO model_versions(version,created_at,artifact_path,metrics_json,training_rows,active) VALUES(?,?,?,?,?,1)",
                       (version, created_at, str(artifact_path), json.dumps(model_metrics), row_count))

    def active_model_training_rows(self) -> int:
        with connect() as db:
            row = db.execute("SELECT training_rows FROM model_versions WHERE active=1 ORDER BY created_at DESC LIMIT 1").fetchone()
        return int(row["training_rows"]) if row else 0

    def training_sample_count(self, feature_names: list[str], horizons: list[int]) -> int:
        rows, _ = training_rows(feature_names, horizons)
        return len(rows)


gold_repository = GoldRepository()
