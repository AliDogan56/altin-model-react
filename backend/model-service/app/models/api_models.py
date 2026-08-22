from pydantic import BaseModel, Field


class PredictIn(BaseModel):
    price: float = Field(gt=0)
    features: dict[str, float]


class TrainIn(BaseModel):
    epochs: int = Field(default=600, ge=100, le=3000)
    minimum_rows: int = Field(default=300, ge=200)
