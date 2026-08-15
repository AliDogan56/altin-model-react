from datetime import datetime

from pydantic import BaseModel, Field


class SnapshotIn(BaseModel):
    model_price: float = Field(gt=0, description="Binance/PAXG model referans fiyatı")
    display_price: float = Field(gt=0, description="Harem ONS kullanıcı fiyatı")
    features: dict[str, float]
    observed_at: datetime | None = None
    source: str = "Binance PAXGUSDT"
    display_source: str = "Harem ONS"


class PredictIn(BaseModel):
    price: float = Field(gt=0)
    features: dict[str, float]


class TrainIn(BaseModel):
    epochs: int = Field(default=250, ge=20, le=2000)
    minimum_rows: int = Field(default=80, ge=30)
