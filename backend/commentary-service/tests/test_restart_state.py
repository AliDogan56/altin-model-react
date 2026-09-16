"""Yeniden başlatma: son üretim zamanı ve fiyatı yayındaki sürümden okunur; ilk döngü tam tur atmaz."""
import datetime as dt

from app.services import budget as b
from app.services import commentary_job_service as job_mod
from app.services.regeneration_policy import should_regenerate

GEN = "2026-09-16T10:23:00+00:00"


def test_restart_seeds_generation_state_from_published_version(monkeypatch):
    monkeypatch.setattr(job_mod.commentary_store, "latest", lambda: {"version": "20260916T102300Z", "generated_at": GEN, "live": {"price": 4300.0}})
    svc = job_mod.CommentaryJobService()
    assert svc.last_generation == GEN and svc.last_generation_price == 4300.0
    state = {"last_generation": svc.last_generation, "last_generation_price": svc.last_generation_price, "force": False}
    now = dt.datetime.fromisoformat(GEN) + dt.timedelta(minutes=30)
    assert should_regenerate(state, now, 4305.0, 0.5, 60, 240) == (False, "asgari aralık dolmadı (30 < 60 dk)")   # eskiden "first_generation"
    assert should_regenerate(state, now + dt.timedelta(minutes=40), 4330.0, 0.5, 60, 240)[0] is True             # %0,7 hareket → üret


def test_restart_without_version_or_with_broken_store_keeps_first_generation(monkeypatch):
    monkeypatch.setattr(job_mod.commentary_store, "latest", lambda: None)
    assert job_mod.CommentaryJobService().last_generation is None
    monkeypatch.setattr(job_mod.commentary_store, "latest", lambda: (_ for _ in ()).throw(OSError("bozuk")))
    svc = job_mod.CommentaryJobService()
    assert svc.last_generation is None
    assert should_regenerate({"last_generation": svc.last_generation, "force": False}, dt.datetime.now(dt.UTC), 4300.0, 0.5, 60, 240) == (True, "first_generation")


def test_narration_skip_message_rounds_down():
    now = dt.datetime(2026, 9, 16, 10, 0, tzinfo=dt.UTC)
    ok, why = b.narration_allowed(now=now, attempts_today=1, max_per_day=8, last_ok=now - dt.timedelta(minutes=89, seconds=36),
                                  min_interval_minutes=90, last_attempt=None, retry_minutes=15, cooldown_until=None)
    assert ok is False and why == "son sesten 89 dk geçti (< 90)"
