"""Fiyatı izler, tetiklenince yorumu yeniden üretir (model-service'teki automatic_learning_service kalıbı)."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import time
import traceback

from ..config import settings
from .commentary_pipeline import LATEST_DIR, prepare_inputs, run_fast_pipeline, run_full_pipeline
from .run_planner import fingerprint_hash, input_fingerprint, plan_run
from .commentary_store import commentary_store
from .narration_service import QuotaExhausted, append_ledger, narrate, read_ledger
from .budget import count_since, day_start, narration_allowed, parse_version, text_allowed
from ..market_constants import LEDGER_DIR
from .live_price_service import current_price
from .llm_config import load_llm_settings
from .regeneration_policy import should_regenerate
from . import commentator_service
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
        self.last_narration_skip = None
        self.last_narration_attempt = None
        self.narration_cooldown_until = None
        self.last_full_at = None
        self.last_fingerprint = None
        self.last_run_plan = None
        self.last_commentator_refresh = None      # yorumcu gözcüsü: son tazeleme (UTC), hata ve özet
        self.last_commentator_error = None
        self.last_commentator_summary = None
        self._load_run_log()
        self.generating = False
        self._force = False
        self._task = None

    def force(self) -> None:
        self._force = True

    def _load_run_log(self) -> None:
        """Yeniden başlatmada son tam turun parmak izi diskten okunur; yoksa ilk tur tam olur."""
        try:
            log_data = json.loads((LATEST_DIR / "run_log.json").read_text())
            self.last_fingerprint = log_data.get("fingerprint")
            if log_data.get("last_full_at"):
                self.last_full_at = dt.datetime.fromisoformat(log_data["last_full_at"])
        except (OSError, ValueError):
            pass

    def _save_run_log(self, fingerprint: dict, mode: str, plan_reason: str) -> None:
        LATEST_DIR.mkdir(parents=True, exist_ok=True)
        (LATEST_DIR / "run_log.json").write_text(json.dumps({"fingerprint": fingerprint, "fingerprint_hash": fingerprint_hash(fingerprint), "mode": mode,
                                                             "reason": plan_reason, "last_full_at": self.last_full_at.isoformat() if self.last_full_at else None}, ensure_ascii=False, indent=2))

    def _generate(self, reason: str) -> dict:
        started = time.time()
        snapshot = build_snapshot()
        prepared = prepare_inputs()
        fingerprint = input_fingerprint(prepared["package"], prepared["headlines"], prepared.get("commentators"))
        now = dt.datetime.now(dt.UTC)
        mode, plan_reason = plan_run(configured_mode=settings.pipeline_mode, force=reason == "force", brief_exists=(LATEST_DIR / "brif.json").exists(),
                                     prev=self.last_fingerprint, cur=fingerprint, last_full_at=self.last_full_at, now=now,
                                     full_max_age_minutes=settings.full_run_max_age_minutes)
        self.last_run_plan = {"mode": mode, "reason": plan_reason}
        log.info("tur planı: %s (%s)", mode, plan_reason)
        data_done = time.time()
        llm = load_llm_settings()
        anchor_output = run_full_pipeline(llm, prepared=prepared) if mode == "full" else run_fast_pipeline(llm, prepared=prepared)
        if mode == "full":
            self.last_full_at, self.last_fingerprint = now, fingerprint
        self._save_run_log(fingerprint, mode, plan_reason)
        generated = time.time()
        durations = {"data": round(data_done - started, 1), "llm": round(generated - data_done, 1), "total": round(generated - started, 1)}
        item = commentary_store.save(anchor_output, snapshot, reason, durations)
        result = {"version": item["version"], "durations_seconds": durations, "usage": item["usage"], "headline": item["headline"], "narration": None,
                  "run_mode": mode, "plan_reason": plan_reason}
        # Ses metinden sonra ve ondan bağımsız: bütçe izin verirse şimdi, vermezse sonraki döngülerde denenir.
        result["narration"] = self.maybe_narrate(item)
        return result

    # --- bütçe ---------------------------------------------------------------------
    def _today(self) -> dt.datetime:
        return day_start(dt.datetime.now(dt.UTC), settings.quota_reset_tz)

    def text_runs_today(self) -> int:
        try:
            return count_since([parse_version(r["version"]) for r in commentary_store.runs()], self._today())
        except Exception:  # noqa: BLE001 — defter okunamazsa sınır uygulanmaz, üretim durmaz
            return 0

    def narration_attempts_today(self) -> tuple[int, dt.datetime | None]:
        rows = read_ledger(LEDGER_DIR)
        stamps = [parse_version(r.get("attempted_at", "")) for r in rows]
        ok_stamps = [s for s, r in zip(stamps, rows) if r.get("ok") == "1"]
        return count_since(stamps, self._today()), (max(s for s in ok_stamps if s) if any(ok_stamps) else None)

    def budget(self) -> dict:
        attempts, last_ok = self.narration_attempts_today()
        now = dt.datetime.now(dt.UTC)
        allowed, why = narration_allowed(now=now, attempts_today=attempts, max_per_day=settings.max_narrations_per_day, last_ok=last_ok,
                                         min_interval_minutes=settings.narrate_min_interval_minutes, last_attempt=self.last_narration_attempt,
                                         retry_minutes=settings.narrate_retry_minutes, cooldown_until=self.narration_cooldown_until)
        return {"reset_tz": settings.quota_reset_tz, "day_start": self._today().isoformat(),
                "text": {"today": self.text_runs_today(), "max_per_day": settings.max_text_runs_per_day},
                "narration": {"attempts_today": attempts, "max_per_day": settings.max_narrations_per_day, "last_ok": last_ok.isoformat() if last_ok else None,
                              "min_interval_minutes": settings.narrate_min_interval_minutes, "allowed_now": allowed, "blocked_reason": why or None,
                              "cooldown_until": self.narration_cooldown_until.isoformat() if self.narration_cooldown_until else None}}

    def maybe_narrate(self, item: dict) -> dict | None:
        """Bütçe izin veriyorsa sesi üretir; 429'da soğumaya girer; her deneme deftere yazılır."""
        if not settings.auto_narrate:
            return None
        attempts, last_ok = self.narration_attempts_today()
        now = dt.datetime.now(dt.UTC)
        allowed, why = narration_allowed(now=now, attempts_today=attempts, max_per_day=settings.max_narrations_per_day, last_ok=last_ok,
                                         min_interval_minutes=settings.narrate_min_interval_minutes, last_attempt=self.last_narration_attempt,
                                         retry_minutes=settings.narrate_retry_minutes, cooldown_until=self.narration_cooldown_until)
        if not allowed:
            self.last_narration_skip = why
            return None
        self.last_narration_attempt = now
        started = time.time()
        try:
            meta = narrate(commentary_store.version_dir(item["version"]), item, api_key=os.getenv("GEMINI_API_KEY", ""),
                           model=settings.tts_model, voice=settings.tts_voice, bitrate_kbps=settings.tts_bitrate_kbps)
            append_ledger(LEDGER_DIR, item["version"], True, time.time() - started, meta["bytes"])
            self.last_narration_error, self.last_narration_skip = None, None
            return meta
        except QuotaExhausted as error:
            self.narration_cooldown_until = now + dt.timedelta(minutes=settings.narrate_cooldown_minutes)
            append_ledger(LEDGER_DIR, item["version"], False, time.time() - started, 0, str(error))
            self.last_narration_error = f"kota: {error}"
            log.warning("TTS kotası; %s dk soğuma", settings.narrate_cooldown_minutes)
        except Exception as error:  # noqa: BLE001
            append_ledger(LEDGER_DIR, item["version"], False, time.time() - started, 0, f"{type(error).__name__}: {error}")
            self.last_narration_error = f"{type(error).__name__}: {error}"
            log.warning("Sesli anlatım üretilemedi: %s", error)
        return None

    def retry_narration_if_missing(self) -> None:
        """Yayındaki sürümün sesi yoksa (bütçe/kota yüzünden ertelenmişse) bir sonraki döngülerde dener."""
        latest = commentary_store.latest()
        if latest and latest.get("narration") is None and settings.auto_narrate:
            self.maybe_narrate(latest)

    def refresh_commentators_if_due(self, now: dt.datetime) -> None:
        """Yorumcu gözcüsü: `COMMENTATOR_REFRESH_MINUTES` aralığıyla (0 = kapalı) RSS + tek LLM çağrısı; hata üretimi durdurmaz,
        15 dk sonra yeniden denenir. Üretimden önce koşar ki ilk tur da özeti görsün."""
        interval = settings.commentator_refresh_minutes
        if interval <= 0:
            return
        if self.last_commentator_refresh and (now - self.last_commentator_refresh) < dt.timedelta(minutes=interval):
            return
        try:
            digest = commentator_service.refresh(load_llm_settings(), now=now)
            self.last_commentator_refresh, self.last_commentator_error = now, None
            self.last_commentator_summary = {"yorumcu": len(digest["yorumcular"]), "kaynak": len(digest["kaynaklar"]), "ozet": digest["ozet_cumle"],
                                             "model": digest.get("model")}
            log.info("yorumcu gözcüsü: %s", self.last_commentator_summary)
        except Exception as error:  # noqa: BLE001
            self.last_commentator_error = f"{type(error).__name__}: {error}"
            self.last_commentator_refresh = now - dt.timedelta(minutes=max(interval - 15, 0))
            log.warning("yorumcu gözcüsü başarısız: %s", error)

    def run_cycle(self) -> dict:
        now = dt.datetime.now(dt.UTC).replace(microsecond=0)
        self.refresh_commentators_if_due(now)
        price = current_price()
        state = {"last_generation": self.last_generation, "last_generation_price": self.last_generation_price, "force": self._force}
        decision, reason = should_regenerate(state, now, price, settings.trigger_move_pct, settings.min_interval_minutes, settings.max_age_minutes,
                                             runs_today=self.text_runs_today(), max_runs_per_day=settings.max_text_runs_per_day)
        self.last_check, self.last_check_price, self.last_decision = now.isoformat(), price, reason
        if not decision:
            self.retry_narration_if_missing()
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
                "last_result": self.last_result, "last_error": self.last_error, "last_narration_error": self.last_narration_error,
                "last_narration_skip": self.last_narration_skip, "budget": self.budget(), "force_pending": self._force,
                "last_run_plan": self.last_run_plan, "last_full_at": self.last_full_at.isoformat() if self.last_full_at else None,
                "full_run_max_age_minutes": settings.full_run_max_age_minutes,
                "commentators": {"refresh_minutes": settings.commentator_refresh_minutes,
                                 "last_refresh": self.last_commentator_refresh.isoformat() if self.last_commentator_refresh else None,
                                 "last_error": self.last_commentator_error, "summary": self.last_commentator_summary},
                "published_version": latest["version"] if latest else None, "published_age_seconds": latest["age_seconds"] if latest else None,
                "llm": load_llm_settings().describe()}


commentary_job_service = CommentaryJobService()
