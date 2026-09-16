"""Mock LLM ile uçtan uca: tam tur → sürüm kaydı → API. Ağ yok; anlık görüntü fixture'dan gelir."""
import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from app.services import commentary_pipeline, commentary_store, market_inputs_service
from app.services.commentary_store import CommentaryStore
from app.services.llm_config import LlmSettings, ProviderConfig, RoleConfig
from tests.conftest import FIXTURES

ROLES = ("technical_analyst", "calendar_news_scout", "macro_analyst", "chief_analyst", "anchor")
EMPTY_INPUTS = {"faiz_beklentisi": {"veri": "yok"}, "enflasyon": {"veri": "yok"}, "takvim": {"olaylar": []}, "pozisyon": {"veri": "yok"}}


def mock_llm() -> LlmSettings:
    return LlmSettings(providers={"m": ProviderConfig("m", "mock")}, roles={r: RoleConfig(r, "m", "mock-1") for r in ROLES + ("commentator_scout",)}, pause_seconds=0)   # gözcü zincirde değil, yalnız doğrulamada


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    latest = tmp_path / "latest"; latest.mkdir()
    for path in FIXTURES.glob("*.json"):
        (latest / path.name).write_text(path.read_text())
    monkeypatch.setattr(commentary_pipeline, "LATEST_DIR", latest)
    monkeypatch.setattr(commentary_store, "VERSIONS_DIR", tmp_path / "versions")
    monkeypatch.setattr(commentary_store, "LEDGER_DIR", tmp_path / "ledger")
    monkeypatch.setattr(commentary_store, "RUNS_CSV", tmp_path / "ledger" / "commentary_runs.csv")
    monkeypatch.setattr(market_inputs_service, "fetch_headlines", lambda *a, **k: [])
    monkeypatch.setattr(market_inputs_service, "collect_market_inputs", lambda *a, **k: EMPTY_INPUTS)
    return tmp_path


def test_full_pipeline_with_mock_and_store(isolated_dirs):
    llm = mock_llm()
    assert llm.validate("full") == []
    result = commentary_pipeline.run_full_pipeline(llm, log=lambda *_: None)
    assert result["run_mode"] == "full" and len(result["sections"]) == 8   # mock brif piyasa_sesleri dolu → sekizinci bölüm and set(result["usage"]) == set(ROLES)
    snapshot = json.loads((FIXTURES / "snapshot.json").read_text())
    store = CommentaryStore()
    item = store.save(result, snapshot, "first_generation", {"data": 1.0, "llm": 2.0, "total": 3.0})
    assert item["version"] and item["live"]["price"] == snapshot["canli"]["fiyat"] and item["official_fix"]["price"] == snapshot["spot_lbma_pm"]["fiyat"]
    latest = store.latest()
    assert latest["version"] == item["version"] and latest["age_seconds"] >= 0 and latest["sections"][0]["id"] == "giris"
    assert (isolated_dirs / "ledger" / "commentary_runs.csv").read_text().count("\n") == 2
    fast = commentary_pipeline.run_fast_pipeline(llm, log=lambda *_: None)
    assert fast["run_mode"] == "fast" and fast["usage"].keys() == {"anchor"}


def test_prune_keeps_only_recent_versions(isolated_dirs, monkeypatch):
    import dataclasses
    from app.services import commentary_store as store_mod
    monkeypatch.setattr(store_mod, "settings", dataclasses.replace(store_mod.settings, keep_versions=2))
    store = CommentaryStore()
    result = commentary_pipeline.run_fast_pipeline(mock_llm(), log=lambda *_: None)
    snapshot = json.loads((FIXTURES / "snapshot.json").read_text())
    versions = []
    for i in range(3):
        import time; time.sleep(1.05)  # sürüm adı saniye çözünürlüklü
        versions.append(store.save(result, snapshot, "force", {"total": 0})["version"])
    dirs = sorted(p.name for p in (isolated_dirs / "versions").iterdir() if p.is_dir() and not p.is_symlink())
    assert dirs[-1] == versions[-1] and len(dirs) <= store_mod.settings.keep_versions
    assert store.latest()["version"] == versions[-1]


def test_api_health_latest_job_and_admin(isolated_dirs):
    from app.main import app
    with TestClient(app) as client:
        assert client.get("/health").json()["service"] == "commentary-service"
        assert client.get("/ready").status_code == 503  # henüz yorum yok
        assert client.get("/v1/commentary/latest").status_code == 404
        result = commentary_pipeline.run_fast_pipeline(mock_llm(), log=lambda *_: None)
        CommentaryStore().save(result, json.loads((FIXTURES / "snapshot.json").read_text()), "force", {"total": 0})
        body = client.get("/v1/commentary/latest").json()
        assert body["run_mode"] == "fast" and len(body["sections"]) == 7   # hızlı tur yedek brifle: yorumcu kaydı yok, sekizinci bölüm atılır and body["disclaimer"]
        assert client.get("/v1/commentary/latest/text").text.startswith(body["title"])
        assert client.get("/ready").status_code == 200
        job = client.get("/v1/commentary/job").json()
        assert job["enabled"] is False and job["published_version"] == body["version"]
        assert client.post("/v1/commentary/regenerate").status_code in (401, 403)
        assert client.post("/v1/commentary/regenerate", headers={"Authorization": "Bearer wrong"}).status_code in (401, 403)
        ok = client.post("/v1/commentary/regenerate", headers={"Authorization": "Bearer test-admin-token"})
        assert ok.status_code == 200 and ok.json()["force_pending"] is True
