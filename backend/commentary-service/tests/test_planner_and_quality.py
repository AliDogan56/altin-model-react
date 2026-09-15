"""Tur planlayıcı, denetim iyileştirmeleri ve şema modu; ağ yok."""
import datetime as dt
import json

import httpx
import pytest

from app.services import commentary_job_service as job_mod
from app.services import llm_gateway as gw
from app.services.llm_config import ProviderConfig
from app.services.output_audit import audit_text
from app.services.run_planner import fingerprint_hash, input_fingerprint, inputs_changed, plan_run

NOW = dt.datetime(2026, 9, 15, 12, 0, tzinfo=dt.UTC)
PKG = {"takvim": {"olaylar": [{"tarih": "2026-09-16", "olay": "faiz"}]}, "faiz_beklentisi": {"tarih": "2026-09-15", "artis_pct": 93.0, "kaynak": "x"},
       "enflasyon": {"yoy": 3.7}, "pozisyon": {"net_uzun": 134972}, "makro_son": {"DFII10": 2.55}, "canli": {"fiyat": 4271.83}}
HS = [{"baslik": f"başlık {i}"} for i in range(8)]


def test_fingerprint_ignores_price_and_dates_but_tracks_inputs():
    fp = input_fingerprint(PKG, HS)
    assert "tarih" not in fp["faiz"] and fp["basliklar"] == sorted(f"başlık {i}" for i in range(6))
    same = input_fingerprint({**PKG, "canli": {"fiyat": 4300.0}, "faiz_beklentisi": {**PKG["faiz_beklentisi"], "tarih": "2026-09-16"}}, HS)
    assert inputs_changed(fp, same) == (False, "girdiler aynı") and fingerprint_hash(fp) == fingerprint_hash(same)
    assert inputs_changed(fp, input_fingerprint({**PKG, "pozisyon": {"net_uzun": 1}}, HS))[1] == "pozisyon değişti"
    two_new = [{"baslik": "yeni 1"}, {"baslik": "yeni 2"}] + HS[:4]
    assert inputs_changed(fp, input_fingerprint(PKG, two_new))[0] is False
    three_new = [{"baslik": "yeni 1"}, {"baslik": "yeni 2"}, {"baslik": "yeni 3"}] + HS[:3]
    assert inputs_changed(fp, input_fingerprint(PKG, three_new)) == (True, "3 yeni başlık")
    assert inputs_changed(None, fp)[0] is True


def test_plan_run_rules():
    fp = input_fingerprint(PKG, HS)
    base = dict(configured_mode="full", force=False, brief_exists=True, prev=fp, cur=fp, last_full_at=NOW - dt.timedelta(minutes=30), now=NOW, full_max_age_minutes=240)
    assert plan_run(**base) == ("fast", "girdiler aynı")
    assert plan_run(**{**base, "force": True}) == ("full", "force")
    assert plan_run(**{**base, "brief_exists": False}) == ("full", "brif yok")
    assert plan_run(**{**base, "cur": input_fingerprint({**PKG, "enflasyon": {"yoy": 4}}, HS)}) == ("full", "enflasyon değişti")
    assert plan_run(**{**base, "last_full_at": NOW - dt.timedelta(minutes=241)})[0] == "full"
    assert plan_run(**{**base, "configured_mode": "fast", "force": True}) == ("fast", "yapılandırma fast")


def test_audit_word_boundaries_and_live_price():
    paket = {"canli": {"fiyat": 4271.83}, "seviye": 4350.98}
    assert audit_text("Dowding raporu ve FedWatch verisi; fiyat 4.272 dolar", paket, live_price=4271.83) == []
    assert "Fed" in audit_text("Fed'in kararı; fiyat 4.271,83 dolar", paket, live_price=4271.83)[0]
    assert "Dow" in audit_text("Dow yükseliş diyor; fiyat 4.272 dolar", paket, live_price=4271.83)[0]
    assert audit_text("ilk direnç 4.350,98 dolar", paket, live_price=4271.83) == ["şu anki fiyat metinde yok: canlı fiyat 4.271,83 dolar girişte ve manşette geçmeli"]
    assert audit_text("sayısız bir gün", paket, live_price=4271.83) == []          # hiç sayı yoksa fiyat kuralı susar (mock çıktısı)
    assert audit_text("fiyat 4.271,8 dolar", paket, live_price=4271.83) == []       # bir ondalık da geçerli


def test_openai_compatible_falls_back_from_json_schema_to_json_object(monkeypatch):
    gw._SCHEMA_MODE.clear()
    seen = []

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, json=None, headers=None):
            seen.append(json.get("response_format"))
            if json.get("response_format", {}).get("type") == "json_schema":
                return httpx.Response(400, request=httpx.Request("POST", url), json={"error": "unsupported"})
            return httpx.Response(200, request=httpx.Request("POST", url), json={"choices": [{"message": {"content": "{\"a\": 1}"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}})
    monkeypatch.setattr(gw.httpx, "Client", FakeClient)
    provider = gw.OpenAICompatibleProvider(ProviderConfig("p", "openai_compatible", base_url="http://x", api_key_env=""))
    text, usage = provider.complete("s", "u", {"type": "object"}, 100, "m")
    assert text == '{"a": 1}' and [s["type"] for s in seen] == ["json_schema", "json_object"]
    assert gw._SCHEMA_MODE["p"] == "json_object"
    provider.complete("s", "u", {"type": "object"}, 100, "m")           # ikinci çağrı doğrudan json_object
    assert [s["type"] for s in seen][-1:] == ["json_object"] and len(seen) == 3


def test_job_chooses_fast_when_inputs_unchanged(tmp_path, monkeypatch):
    latest = tmp_path / "latest"; latest.mkdir()
    (latest / "brif.json").write_text("{}")
    monkeypatch.setattr(job_mod, "LATEST_DIR", latest)
    monkeypatch.setattr(job_mod, "build_snapshot", lambda: {})
    monkeypatch.setattr(job_mod, "prepare_inputs", lambda: {"package": PKG, "headlines": HS})
    monkeypatch.setattr(job_mod, "load_llm_settings", lambda: None)
    calls = []
    monkeypatch.setattr(job_mod, "run_full_pipeline", lambda llm, prepared=None: (calls.append("full") or {"headline": "h", "sections": [], "usage": {}, "run_mode": "full"}))
    monkeypatch.setattr(job_mod, "run_fast_pipeline", lambda llm, prepared=None: (calls.append("fast") or {"headline": "h", "sections": [], "usage": {}, "run_mode": "fast"}))
    saved = []
    class Store:
        def save(self, out, snap, reason, durations): saved.append(out); return {"version": "v", "usage": {}, "headline": "h", "trigger": {}, "durations_seconds": durations}
        def version_dir(self, v): return tmp_path
    monkeypatch.setattr(job_mod, "commentary_store", Store())
    monkeypatch.setattr(job_mod, "settings", __import__("dataclasses").replace(job_mod.settings, auto_narrate=False))
    svc = job_mod.CommentaryJobService()
    assert svc._generate("first_generation")["run_mode"] == "full" and calls == ["full"]
    assert svc._generate("fiyat oynadı")["run_mode"] == "fast" and calls == ["full", "fast"]
    assert svc._generate("force")["run_mode"] == "full"
    log_data = json.loads((latest / "run_log.json").read_text())
    assert log_data["mode"] == "full" and log_data["fingerprint"]["pozisyon"] == {"net_uzun": 134972}
    # yeniden başlatma: parmak izi diskten okunur, sonraki tur hızlı olur
    svc2 = job_mod.CommentaryJobService()
    assert svc2.last_fingerprint is not None and svc2._generate("fiyat")["run_mode"] == "fast"


def test_budget_problems_only_for_severe_shortfall():
    from app.services.commentary_pipeline import budget_problems
    ok = [{"id": "neden", "metin": " ".join(["kelime"] * 64)}, {"id": "kapanis", "metin": " ".join(["k"] * 21)}]
    assert budget_problems(ok) == []
    kisa = [{"id": "neden", "metin": "çok kısa"}, {"id": "giris", "metin": " ".join(["k"] * 40)}]
    out = budget_problems(kisa)
    assert len(out) == 1 and "neden 2 kelime (en az 90)" in out[0] and "giris" not in out[0]
