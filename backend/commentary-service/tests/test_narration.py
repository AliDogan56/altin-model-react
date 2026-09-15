"""Sesli anlatım: metin parçalama, zaman tahmini, MP3 kodlama, saklama ve uç; ağa çıkılmaz."""
import json
import math
import struct

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import commentary_store as store_mod
from app.services import narration_service as ns
from app.services.commentary_store import commentary_store

ITEM = {"version": "20260915T100000Z", "headline": "Manşet cümlesi.", "summary": "Özet metni burada.",
        "sections": [{"id": "giris", "title": "Giriş", "text": "İlk bölüm."}, {"id": "kapanis", "title": "Sonuç", "text": "Son söz."}]}


def _pcm(seconds: float, rate: int = 24000) -> bytes:
    n = int(seconds * rate)
    return b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(n))


def test_segments_and_text():
    segs = ns.narration_segments(ITEM)
    assert [s["id"] for s in segs] == ["headline", "summary", "giris", "kapanis"]
    assert segs[2]["text"] == "Giriş. İlk bölüm."
    text = ns.narration_text(segs)
    assert text.startswith("Manşet cümlesi.\n\nÖzet metni burada.") and text.endswith("Sonuç. Son söz.")
    assert segs[-1]["end_char"] == len(text)
    assert ns.narration_segments({"headline": "", "summary": "", "sections": []}) == []


def test_estimated_times_are_monotone_and_span_duration():
    segs = ns.narration_segments(ITEM)
    times = ns.estimate_times(segs, 60.0)
    assert times[0]["start"] == 0 and times[-1]["end"] == 60.0
    assert all(a["end"] <= b["start"] for a, b in zip(times, times[1:]))


def test_encode_mp3_produces_frames_and_shrinks():
    pcm = _pcm(1.0)
    mp3 = ns.encode_mp3(pcm, 24000, bitrate_kbps=48)
    assert mp3[:1] == b"\xff" and len(mp3) < len(pcm) / 4
    assert 4000 < len(mp3) < 12000   # 48 kbps × 1 sn ≈ 6 KB


def test_narrate_writes_files_and_store_exposes_meta(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "VERSIONS_DIR", tmp_path / "versions")
    version_dir = tmp_path / "versions" / ITEM["version"]
    version_dir.mkdir(parents=True)
    (version_dir / "commentary.json").write_text(json.dumps({**ITEM, "generated_at": "2026-09-15T10:00:00+00:00", "title": "T", "disclaimer": "D",
                                                              "as_of": "2026-09-15", "run_mode": "full", "trigger": {}, "usage": {}, "durations_seconds": {}}))
    (tmp_path / "versions" / "current").symlink_to(ITEM["version"])
    calls = []

    def fake_synth(text, *, api_key, model, voice, **kw):
        calls.append((text, api_key, model, voice))
        return _pcm(2.0), 24000

    monkeypatch.setattr(ns, "synthesize_pcm", fake_synth)
    meta = ns.narrate(version_dir, ITEM, api_key="k", model="m", voice="Kore", bitrate_kbps=48)
    assert calls[0][1:] == ("k", "m", "Kore") and calls[0][0].startswith("Manşet")
    assert meta["duration_seconds"] == pytest.approx(2.0) and meta["voice"] == "Kore" and meta["estimated"] is True
    assert (version_dir / "commentary.mp3").stat().st_size == meta["bytes"] > 0
    assert [s["id"] for s in meta["segments"]] == ["headline", "summary", "giris", "kapanis"]
    latest = commentary_store.latest()
    assert latest["narration"]["voice"] == "Kore" and latest["narration"]["segments"][-1]["end"] == pytest.approx(2.0)
    assert commentary_store.latest_audio() == version_dir / "commentary.mp3"
    client = TestClient(app)
    r = client.get("/v1/commentary/latest/audio")
    assert r.status_code == 200 and r.headers["content-type"].startswith("audio/mpeg") and r.headers["etag"] == f'"{ITEM["version"]}"'
    assert r.content[:1] == b"\xff"
    body = client.get("/v1/commentary/latest").json()
    assert body["narration"]["duration_seconds"] == pytest.approx(2.0)


def test_audio_404_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "VERSIONS_DIR", tmp_path / "versions")
    (tmp_path / "versions").mkdir()
    assert TestClient(app).get("/v1/commentary/latest/audio").status_code == 404


def test_synthesize_retries_on_429_then_parses(monkeypatch):
    import httpx
    responses = [httpx.Response(429, headers={"retry-after": "0"}, request=httpx.Request("POST", "http://x")),
                 httpx.Response(200, json={"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/l16; rate=24000", "data": "AAAA"}}]}}]},
                                request=httpx.Request("POST", "http://x"))]
    monkeypatch.setattr(ns.httpx, "post", lambda *a, **k: responses.pop(0))
    monkeypatch.setattr(ns.time, "sleep", lambda s: None)
    pcm, rate = ns.synthesize_pcm("metin", api_key="k", model="m", voice="Kore")
    assert pcm == b"\x00\x00\x00" and rate == 24000


def test_synthesize_gives_up_after_attempts(monkeypatch):
    import httpx
    monkeypatch.setattr(ns.httpx, "post", lambda *a, **k: httpx.Response(503, request=httpx.Request("POST", "http://x")))
    monkeypatch.setattr(ns.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        ns.synthesize_pcm("metin", api_key="k", model="m", voice="Kore", attempts=2)
