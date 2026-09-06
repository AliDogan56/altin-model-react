"""XAU/USD veri setini yeniler ve yeterli yeni etiket oluşunca modeli eğitir."""
import asyncio
import hashlib
import json
from datetime import datetime, timezone

from ..config import ROOT, settings
from .model_service import model_service
from .trainer import train_model, _load_dataset
from .xau_dataset_service import HORIZONS, write_csv

DATASET = ROOT / "data" / "xauusd_training_5y.csv"


class AutomaticLearningService:
    def __init__(self):
        self.last_run = None
        self.last_error = None
        self.last_result = None
        self._task = None
        self._candidate = None

    def _last_candidate(self):
        try:
            self._candidate = json.loads((settings.model_dir / "last_candidate.json").read_text())
        except (OSError, ValueError):
            self._candidate = self._candidate or {}
        return self._candidate

    def _refresh_and_train(self):
        count = write_csv(DATASET)
        rows, _ = _load_dataset(DATASET)
        snapshot_hash = hashlib.sha256(DATASET.read_bytes()).hexdigest()
        candidate = self._last_candidate()
        references = [model_service.active or {}, candidate]
        # A rolling five-year dataset can stay exactly the same size while its
        # newest matured labels advance. Count label dates, never net row growth.
        new_labels = {}
        for horizon in HORIZONS:
            cutoff = max((reference.get("training_end", {}).get(str(horizon), "")
                          for reference in references), default="")
            new_labels[str(horizon)] = sum(row["date"] > cutoff and row.get(f"target_return_{horizon}d", "") != ""
                                            for row in rows)
        trained = (settings.auto_train and candidate.get("dataset_hash") != snapshot_hash
                   and min(new_labels.values()) >= settings.retrain_every_new_rows)
        # minimum_rows daha önce geçilmiyordu: RETRAIN_MINIMUM_ROWS yalnız elle
        # tetiklenen eğitimde etkiliydi, saatlik job her zaman koddaki varsayılanı
        # kullanıyordu.
        result = (train_model(minimum_rows=settings.retrain_minimum_rows, dataset_path=DATASET, promote=False) if trained
                  else {"training_rows": count, "trained": False, "new_labels_by_horizon": new_labels})
        if trained:
            # Auto-learning prepares evidence, not a replacement for the champion.
            self._candidate = result
            result = {**result, "trained": True, "promoted": False}
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
