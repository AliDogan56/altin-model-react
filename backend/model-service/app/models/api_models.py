from datetime import date
from pydantic import BaseModel, Field, FiniteFloat


class PredictIn(BaseModel):
    price: FiniteFloat = Field(gt=0)
    features: dict[str, FiniteFloat]
    # A supplied vector is always a client scenario, never an official forecast.
    source_date: date | None = None


class TrainIn(BaseModel):
    epochs: int = Field(default=600, ge=100, le=3000)
    minimum_rows: int = Field(default=300, ge=200)
