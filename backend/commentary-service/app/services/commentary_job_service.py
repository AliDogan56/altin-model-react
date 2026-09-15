"""Fiyatı izler, tetiklenince yorumu yeniden üretir (model-service'teki automatic_learning_service kalıbı)."""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
import time
import traceback

from ..config import settings
from .commentary_pipeline import run_fast_pipeline, run_full_pipeline
from .commentary_store import commentary_store
from .narration_service import narrate
from .live_price_service import current_price
from .llm_config import load_llm_settings
from .regeneration_policy import should_regenerate
from .snapshot_service import build_snapshot


log = logging.getLogger(__name__)


class CommentaryJobService:
    def __init__(self):
        self.last_check = None
        self.last_check_price = None
        self.last_decision = None
        self.last_generation = None
        self.last_generation_price = None
        self.last_result = None
        self.last_error = None
        self.last_narration_error = None
        self.generating = False
        self._force = False
        self._task = None

    def force(self) -> None:
        self._force = True

    def _generate(self, reason: str) -> dict:
        started = time.time()
        snapshot = build_snapshot()
        data_done = time.time()
        llm = load_llm_settings()
        anchor_output = run_full_pipeline(llm) if settings.pipeline_mode == "full" else run_fast_pipeline(llm)
        generated = time.time()
        durations = {"data": round(data_done - started, 1), "llm": round(generated - data_done, 1), "total": round(generated - started, 1)}
        item = commentary_store.save(anchor_output, snapshot, reason, durations)
        result = {"version": item["version"], "durations_seconds": durations, "usage": item["usage"], "headline": item["headline"], "narration": None}
        # Ses metinden sonra ve ondan bağımsız: TTS düşerse metin yayında kalır, hata ayrı raporlanır.
        if settings.auto_narrate:
            try:
                result["narration"] = narrate(commentary_store.version_dir(item["version"]), item, api_key=os.getenv("GEMINI_API_KEY", ""),
                                              model=settings.tts_model, voice=settings.tts_voice, bitrate_kbps=settings.tts_bitrate_kbps)
                self.last_narration_error = None
            except Exception as error:  # noqa: BLE001
                self.last_narration_error = f"{type(error).__name__}: {error}"
                log.warning("Sesli anlatım üretilemedi: %s", error)
        return result

    def run_cycle(self) -> dict:
        now = dt.datetime.now(dt.UTC).replace(microsecond=0)
        price = current_price()
        state = {"last_generation": self.last_generation, "last_generation_price": self.last_generation_price, "force": self._force}
        decision, reason = should_regenerate(state, now, price, settings.trigger_move_pct, settings.min_interval_minutes, settings.max_age_minutes)
        self.last_check, self.last_check_price, self.last_decision = now.isoformat(), price, reason
        if not decision:
            return {"generated": False, "reason": reason, "price": price}
        self.generating = True
        try:
            self.last_result = self._generate(reason)
            self.last_generation, self.last_generation_price, self.last_error, self._force = now.isoformat(), price, None, False
        except Exception as error:  # noqa: BLE001
            self.last_error = f"{type(error).__name__}: {error}"
            self.last_error_trace = traceback.format_exc()[-800:]
        finally:
            self.generating = False
        return {"generated": self.last_error is None, "reason": reason, "price": price, "error": self.last_error}

    async def _loop(self):
        await asyncio.sleep(2)
        while True:
            try:
                await asyncio.to_thread(self.run_cycle)
            except Exception as error:  # noqa: BLE001
                self.last_error = f"{type(error).__name__}: {error}"
            await asyncio.sleep(settings.check_interval_seconds)

    def start(self):
        if settings.auto_generate and (not self._task or self._task.done()):
            self._task = asyncio.create_task(self._loop(), name="commentary-job")

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def status(self) -> dict:
        latest = commentary_store.latest()
        return {"enabled": settings.auto_generate, "pipeline_mode": settings.pipeline_mode, "check_interval_seconds": settings.check_interval_seconds,
                "trigger": {"move_pct": settings.trigger_move_pct, "min_interval_minutes": settings.min_interval_minutes, "max_age_minutes": settings.max_age_minutes},
                "last_check": self.last_check, "last_check_price": self.last_check_price, "last_decision": self.last_decision,
                "last_generation": self.last_generation, "last_generation_price": self.last_generation_price, "generating": self.generating,
                "last_result": self.last_result, "last_error": self.last_error, "last_narration_error": self.last_narration_error, "force_pending": self._force,
                "published_version": latest["version"] if latest else None, "published_age_seconds": latest["age_seconds"] if latest else None,
                "llm": load_llm_settings().describe()}


commentary_job_service = CommentaryJobService()
