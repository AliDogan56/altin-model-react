import asyncio
import csv
import io
import math
from datetime import datetime, timezone
from statistics import fmean, pstdev

import httpx

from ..config import settings
from ..models.api_models import SnapshotIn, TrainIn
from ..repositories.gold_repository import gold_repository
from .learning_service import learning_service
from .model_service import model_service
from .prediction_service import prediction_service

FRED_IDS = ["DGS10", "DGS2", "DFII10", "DTWEXBGS", "DCOILWTICO", "VIXCLS", "FEDFUNDS", "CPIAUCSL", "CPILFESL", "PPIACO", "PCEPI", "UNRATE", "PAYEMS", "RSAFS"]


def _fred_values(text: str) -> list[float]:
    values = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            values.append(float(list(row.values())[-1]))
        except (ValueError, IndexError, TypeError):
            continue
    return values


class AutomaticLearningService:
    def __init__(self) -> None:
        self.last_run: str | None = None
        self.last_error: str | None = None
        self._task: asyncio.Task | None = None

    async def _gateway_json(self, path: str):
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{settings.gateway_url}{path}")
            response.raise_for_status()
            return response.json()

    async def _gateway_text(self, path: str) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{settings.gateway_url}{path}")
            response.raise_for_status()
            return response.text

    async def collect_once(self) -> dict:
        candles = await self._gateway_json("/market-service/v1/market/binance")
        closes = [float(row[4]) for row in candles]
        highs = [float(row[2]) for row in candles]
        lows = [float(row[3]) for row in candles]
        volumes = [math.log1p(float(row[5])) for row in candles]
        last = len(closes) - 1
        returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        differences = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [max(0.0, value) for value in differences[-14:]]
        losses = [max(0.0, -value) for value in differences[-14:]]
        rs = fmean(gains) / (fmean(losses) or 1e-9)
        true_ranges = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])) for i in range(1, len(closes))]
        features = dict(model_service.initial["latest"])
        features.update({
            "gold_return_1d": closes[last] / closes[last - 1] - 1,
            "gold_return_5d": closes[last] / closes[last - 5] - 1,
            "gold_return_20d": closes[last] / closes[last - 20] - 1,
            "gold_return_60d": closes[last] / closes[last - 60] - 1,
            "gold_ma_ratio_20d": closes[last] / fmean(closes[-20:]) - 1,
            "gold_ma_ratio_50d": closes[last] / fmean(closes[-50:]) - 1,
            "gold_ma_ratio_200d": closes[last] / fmean(closes[-200:]) - 1,
            "gold_rsi14": 100 - 100 / (1 + rs),
            "gold_atr14_pct": fmean(true_ranges[-14:]) / closes[last],
            "gold_volatility_20d": pstdev(returns[-20:]) * math.sqrt(365),
            "gold_volume_z20": (volumes[-1] - fmean(volumes[-20:])) / (pstdev(volumes[-20:]) or 1),
        })
        series = {series_id: _fred_values(await self._gateway_text(f"/market-service/v1/market/fred?id={series_id}")) for series_id in FRED_IDS}
        latest = lambda key: series[key][-1]
        change = lambda key, periods: latest(key) - series[key][-1 - periods]
        ratio = lambda key, periods: latest(key) / series[key][-1 - periods] - 1
        yoy = lambda key: (latest(key) / series[key][-13] - 1) * 100
        for key in ["DGS10", "DGS2", "DFII10", "DTWEXBGS", "DCOILWTICO", "VIXCLS", "FEDFUNDS", "UNRATE"]:
            features[key] = latest(key)
        features.update({"CPIAUCSL_yoy_pct": yoy("CPIAUCSL"), "CPILFESL_yoy_pct": yoy("CPILFESL"),
                         "PPIACO_yoy_pct": yoy("PPIACO"), "PCEPI_yoy_pct": yoy("PCEPI"),
                         "PAYEMS_change_k": change("PAYEMS", 1), "RSAFS_mom_pct": ratio("RSAFS", 1) * 100,
                         "yield_curve_10y_2y": latest("DGS10") - latest("DGS2"),
                         "breakeven_inflation_10y": latest("DGS10") - latest("DFII10"),
                         "real_yield_change_5d": change("DFII10", 5), "dollar_return_5d": ratio("DTWEXBGS", 5),
                         "oil_return_5d": ratio("DCOILWTICO", 5), "vix_change_5d": change("VIXCLS", 5)})
        result = prediction_service.save_snapshot(SnapshotIn(model_price=closes[-1], display_price=closes[-1], features=features,
                                                              observed_at=datetime.now(timezone.utc), source="Binance PAXGUSDT",
                                                              display_source="Otomatik model job'u"))
        self.last_run, self.last_error = datetime.now(timezone.utc).isoformat(), None
        return result

    def retrain_if_ready(self) -> dict:
        count = gold_repository.training_sample_count(model_service.features, model_service.horizons)
        active_rows = gold_repository.active_model_training_rows()
        if count < settings.retrain_minimum_rows or count - active_rows < settings.retrain_every_new_rows:
            return {"trained": False, "available_rows": count, "active_model_rows": active_rows}
        result = learning_service.train(TrainIn(epochs=250, minimum_rows=settings.retrain_minimum_rows))
        return {"trained": True, **result}

    async def run_cycle(self) -> None:
        await self.collect_once()
        if settings.auto_train:
            await asyncio.to_thread(self.retrain_if_ready)

    async def _loop(self) -> None:
        await asyncio.sleep(2)
        while True:
            try:
                await self.run_cycle()
            except Exception as error:
                self.last_error = f"{type(error).__name__}: {error}"
            await asyncio.sleep(settings.collection_interval_seconds)

    def start(self) -> None:
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="automatic-model-learning")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def status(self) -> dict:
        return {"enabled": settings.auto_train, "interval_seconds": settings.collection_interval_seconds,
                "last_run": self.last_run, "last_error": self.last_error}


automatic_learning_service = AutomaticLearningService()
