"""Kota bütçesi: gün sınırı, ses aralığı, soğuma, ertelenmiş deneme; ağ yok."""
import dataclasses
import datetime as dt
import json

from app.services import budget as b
from app.services import commentary_job_service as job_mod
from app.services import commentary_store as store_mod
from app.services import narration_service as ns
from app.services.regeneration_policy import should_regenerate

NOW = dt.datetime(2026, 9, 15, 12, 0, tzinfo=dt.UTC)


def test_day_start_follows_reset_timezone():
    # 15 Eylül 12:00 UTC = 05:00 Pasifik → gün 07:00 UTC'de başladı
    assert b.day_start(NOW, "America/Los_Angeles") == dt.datetime(2026, 9, 15, 7, 0, tzinfo=dt.UTC)
    assert b.day_start(NOW, "UTC") == dt.datetime(2026, 9, 15, 0, 0, tzinfo=dt.UTC)
    assert b.parse_version("20260915T070122Z") == dt.datetime(2026, 9, 15, 7, 1, 22, tzinfo=dt.UTC)
    assert b.parse_version("bozuk") is None
    assert b.count_since([b.parse_version(v) for v in ("20260915T065959Z", "20260915T070000Z", "20260915T110000Z", "x")], b.day_start(NOW, "America/Los_Angeles")) == 2


def test_text_cap_blocks_but_force_passes():
    assert b.text_allowed(11, 12) == (True, "")
    assert b.text_allowed(12, 12)[0] is False and "12/12" in b.text_allowed(12, 12)[1]
    assert b.text_allowed(99, 12, force=True) == (True, "force")
    assert b.text_allowed(99, 0) == (True, "")
    state = {"last_generation": "2026-09-15T08:00:00+00:00", "last_generation_price": 4000.0}
    ok, why = should_regenerate(state, NOW, 4100.0, 0.5, 60, 240, runs_today=12, max_runs_per_day=12)
    assert ok is False and "günlük metin sınırı" in why
    assert should_regenerate(state, NOW, 4100.0, 0.5, 60, 240, runs_today=5, max_runs_per_day=12)[0] is True
    assert should_regenerate({**state, "force": True}, NOW, None, 0.5, 60, 240, runs_today=12, max_runs_per_day=12) == (True, "force")


def test_narration_allowed_rules():
    base = dict(now=NOW, attempts_today=0, max_per_day=8, last_ok=None, min_interval_minutes=90, last_attempt=None, retry_minutes=15, cooldown_until=None)
    assert b.narration_allowed(**base) == (True, "")
    assert "günlük ses sınırı" in b.narration_allowed(**{**base, "attempts_today": 8})[1]
    assert "son sesten" in b.narration_allowed(**{**base, "last_ok": NOW - dt.timedelta(minutes=30)})[1]
    assert b.narration_allowed(**{**base, "last_ok": NOW - dt.timedelta(minutes=91)})[0] is True
    assert "yeniden deneme" in b.narration_allowed(**{**base, "last_attempt": NOW - dt.timedelta(minutes=5)})[1]
    assert "soğuma" in b.narration_allowed(**{**base, "cooldown_until": NOW + dt.timedelta(minutes=20)})[1]
    assert b.narration_allowed(**{**base, "cooldown_until": NOW - dt.timedelta(minutes=1)})[0] is True


def _publish(tmp_path, monkeypatch, version="20260915T110000Z"):
    monkeypatch.setattr(store_mod, "VERSIONS_DIR", tmp_path / "versions")
    monkeypatch.setattr(store_mod, "RUNS_CSV", tmp_path / "ledger" / "commentary_runs.csv")
    monkeypatch.setattr(job_mod, "LEDGER_DIR", tmp_path / "ledger")
    vdir = tmp_path / "versions" / version
    vdir.mkdir(parents=True)
    item = {"version": version, "generated_at": "2026-09-15T11:00:00+00:00", "headline": "H", "summary": "S", "sections": [{"id": "a", "title": "A", "text": "T"}],
            "title": "T", "disclaimer": "D", "as_of": "2026-09-15", "run_mode": "full", "trigger": {}, "usage": {}, "durations_seconds": {}}
    (vdir / "commentary.json").write_text(json.dumps(item))
    (tmp_path / "versions" / "current").symlink_to(version)
    return item


def test_maybe_narrate_respects_budget_and_cooldown(tmp_path, monkeypatch):
    item = _publish(tmp_path, monkeypatch)
    svc = job_mod.CommentaryJobService()
    monkeypatch.setattr(job_mod, "settings", dataclasses.replace(job_mod.settings, auto_narrate=True, max_narrations_per_day=2, narrate_min_interval_minutes=0, narrate_retry_minutes=0))
    calls = []
    monkeypatch.setattr(job_mod, "narrate", lambda vdir, it, **kw: (calls.append(it["version"]) or {"bytes": 10, "duration_seconds": 1.0, "segments": []}))
    assert svc.maybe_narrate(item)["bytes"] == 10 and calls == [item["version"]]
    assert svc.budget()["narration"]["attempts_today"] == 1
    # 429 → soğuma: sonraki deneme engellenir, defter başarısız denemeyi de sayar
    monkeypatch.setattr(job_mod, "narrate", lambda *a, **k: (_ for _ in ()).throw(ns.QuotaExhausted("429")))
    assert svc.maybe_narrate(item) is None and svc.narration_cooldown_until is not None and "kota" in svc.last_narration_error
    assert svc.maybe_narrate(item) is None and "soğuma" in svc.last_narration_skip
    assert svc.budget()["narration"]["attempts_today"] == 2 and svc.budget()["narration"]["allowed_now"] is False


def test_retry_when_audio_missing_and_daily_cap(tmp_path, monkeypatch):
    item = _publish(tmp_path, monkeypatch)
    svc = job_mod.CommentaryJobService()
    monkeypatch.setattr(job_mod, "settings", dataclasses.replace(job_mod.settings, auto_narrate=True, max_narrations_per_day=1, narrate_min_interval_minutes=0, narrate_retry_minutes=0))
    calls = []

    def fake(vdir, it, **kw):
        calls.append(it["version"]); meta = {"bytes": 5, "duration_seconds": 1.0, "segments": [], "voice": "Kore", "model": "m", "estimated": True, "bitrate_kbps": 48}
        (vdir / ns.NARRATION_FILE).write_bytes(b"x"); (vdir / ns.NARRATION_META).write_text(json.dumps(meta)); return meta
    monkeypatch.setattr(job_mod, "narrate", fake)
    svc.retry_narration_if_missing()          # ses yok → üretir
    assert calls == [item["version"]]
    svc.retry_narration_if_missing()          # ses var → dokunmaz
    assert calls == [item["version"]]
    # yeni sürüm, günlük sınır 1 dolu → atlanır, sebep yazılır
    item2 = {**item, "version": "20260915T120000Z"}
    (tmp_path / "versions" / item2["version"]).mkdir()
    assert svc.maybe_narrate(item2) is None and "günlük ses sınırı" in svc.last_narration_skip
