"""XAU/USD veri setini yeniler ve yeterli yeni etiket oluşunca modeli eğitir."""
import asyncio
from datetime import datetime, timezone

from ..config import ROOT, settings
from .model_service import model_service
from .trainer import train_model
from .xau_dataset_service import write_csv

DATASET = ROOT / "data" / "xauusd_training_5y.csv"


class AutomaticLearningService:
    def __init__(self):
        self.last_run = None
        self.last_error = None
        self.last_result = None
        self._task = None

    def _refresh_and_train(self):
        rows = write_csv(DATASET)
        previous_rows = int(model_service.active.get("dataset_rows", 0)) if model_service.active else 0
        trained = settings.auto_train and rows - previous_rows >= settings.retrain_every_new_rows
        # minimum_rows daha önce geçilmiyordu: RETRAIN_MINIMUM_ROWS yalnız elle
        # tetiklenen eğitimde etkiliydi, saatlik job her zaman koddaki varsayılanı
        # kullanıyordu.
        result = (train_model(minimum_rows=settings.retrain_minimum_rows) if trained
                  else {"training_rows": rows, "trained": False})
        if trained:
            model_service.reload()
        self.last_result = result
        return result

    async def run_cycle(self):
        result = await asyncio.to_thread(self._refresh_and_train)
        self.last_run, self.last_error = datetime.now(timezone.utc).isoformat(), None
        return result

    async def _loop(self):
        await asyncio.sleep(2)
        while True:
            try: await self.run_cycle()
            except Exception as error: self.last_error = f"{type(error).__name__}: {error}"
            await asyncio.sleep(settings.collection_interval_seconds)

    def start(self):
        if not self._task or self._task.done(): self._task = asyncio.create_task(self._loop(), name="xauusd-learning")

    async def stop(self):
        if self._task:
            self._task.cancel()
            try: await self._task
            except asyncio.CancelledError: pass

    def status(self):
        return {"enabled": settings.auto_train, "source": "XAU/USD",
                "interval_seconds": settings.collection_interval_seconds,
                "last_run": self.last_run, "last_error": self.last_error,
                "last_result": self.last_result,
                "active_model": model_service.version,
                "rejected_artifacts": list(getattr(model_service, "rejected", []))}


automatic_learning_service = AutomaticLearningService()
