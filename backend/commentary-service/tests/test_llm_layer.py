import datetime as dt
import json

from app.services.commentary_pipeline import SUNUM_SCHEMA
from app.services.llm_config import LlmSettings, ProviderConfig, RoleConfig, load_llm_settings
from app.services.llm_gateway import MockProvider, TokenUsage, ask, parse_json
from app.services.news_service import parse_rss
from app.services.output_audit import audit_text
from app.services.regeneration_policy import should_regenerate

RSS = """<rss><channel><item><title>Gold falls 2% as Fed hike bets grow - Reuters</title><link>https://x/1</link><pubDate>Mon, 14 Sep 2026 13:00:00 GMT</pubDate><source url="https://reuters.com">Reuters</source></item>
<item><title>Altın düştü - AA</title><link>https://x/2</link><pubDate>Mon, 14 Sep 2026 12:00:00 GMT</pubDate></item></channel></rss>"""


def test_should_regenerate_rules():
    now = dt.datetime(2026, 9, 14, 15, 0, tzinfo=dt.UTC)
    assert should_regenerate({}, now, 4300, 0.5, 60, 240) == (True, "first_generation")
    state = {"last_generation": (now - dt.timedelta(minutes=30)).isoformat(), "last_generation_price": 4300}
    assert should_regenerate(state, now, 4200, 0.5, 60, 240)[0] is False  # asgari aralık dolmadı
    state["last_generation"] = (now - dt.timedelta(minutes=61)).isoformat()
    assert should_regenerate(state, now, 4330, 0.5, 60, 240)[0] is True   # %0,7 > eşik
    assert should_regenerate(state, now, 4310, 0.5, 60, 240)[0] is False  # %0,23 < eşik
    state["last_generation"] = (now - dt.timedelta(minutes=241)).isoformat()
    assert should_regenerate(state, now, 4301, 0.5, 60, 240)[0] is True   # azami yaş
    assert should_regenerate(state, now, 4301, 0.5, 60, 0)[0] is False    # azami yaş kapalı
    assert should_regenerate({"force": True, **state}, now, 4300, 0.5, 60, 240) == (True, "force")


def test_parse_rss_and_json():
    items = parse_rss(RSS, "en")
    assert items[0]["kaynak"] == "Reuters" and items[1]["kaynak"] == "AA"
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Metin başı {"a": {"b": 2}} sonu') == {"a": {"b": 2}}


def test_llm_settings_load_validate_and_chain(tmp_path, monkeypatch):
    cfg = tmp_path / "llm.toml"
    cfg.write_text('[llm.providers.m]\nkind = "mock"\n[llm.providers.g]\nkind = "openai_compatible"\nbase_url = "https://x/v1"\napi_key_env = "G_KEY"\n'
                   + "".join(f'[llm.roles.{r}]\nprovider = "m"\nmodel = "mock-1"\n' for r in ("technical_analyst", "calendar_news_scout", "macro_analyst", "chief_analyst", "commentator_scout"))
                   + '[llm.roles.anchor]\nprovider = "m"\nmodel = "mock-1"\nfallbacks = [ { provider = "g", model = "llama" } ]\n')
    monkeypatch.delenv("G_KEY", raising=False)
    llm = load_llm_settings(cfg)
    assert llm.roles["anchor"].chain() == [("m", "mock-1"), ("g", "llama")]
    assert any("G_KEY" in p for p in llm.validate("full"))
    monkeypatch.setenv("G_KEY", "x")
    assert llm.validate("full") == [] and llm.validate("fast") == []
    assert llm.describe()["roles"]["anchor"] == ["m/mock-1", "g/llama"]


def test_validate_reports_missing_role_and_bad_kind():
    llm = LlmSettings(providers={"p": ProviderConfig("p", "unknown")}, roles={"anchor": RoleConfig("anchor", "p", "x")})
    problems = llm.validate("full")
    assert any("technical_analyst" in p for p in problems) and any("kind geçersiz" in p for p in problems)


def test_mock_provider_schema_and_ask_fallback():
    text, usage = MockProvider(ProviderConfig("m", "mock")).complete("s", "u", SUNUM_SCHEMA, 100, "mock")
    assert [b["id"] for b in json.loads(text)["bolumler"]] == ["giris", "neden", "masa", "seviyeler", "buyuk_resim", "sesler", "takvim", "kapanis"]
    assert usage.finish_reason == "stop" and (usage + TokenUsage(1, 2, 3)).output_tokens == usage.output_tokens + 2
    llm = LlmSettings(providers={"broken": ProviderConfig("broken", "openai_compatible", base_url="http://127.0.0.1:9/v1"), "m": ProviderConfig("m", "mock")},
                      roles={"anchor": RoleConfig("anchor", "broken", "x", fallbacks=[{"provider": "m", "model": "mock-1"}])})
    text, usage, model = ask(llm, "anchor", "s", "u", SUNUM_SCHEMA)
    assert model == "m/mock-1" and "bolumler" in json.loads(text)


def test_audit_flags_unknown_numbers_and_jargon():
    package = {"canli": {"fiyat": 4295.0, "fikse_gore_pct": -2.28}, "seviyeler": [{"spot_esdeger": 4365.5}], "kanit": "olasılık yüzde 86"}
    assert audit_text("Altın 4.295 dolar, yüzde 2,3 düştü; 4.366 kırıldı; olasılık yüzde 86; 16 Eylül.", package) == []
    problems = audit_text("Fed olasılığı yüzde 35; ATR bir; fiyat 4.100 dolar", package)
    assert any("4.100" in x and "35" in x for x in problems) and any("ATR" in x for x in problems)
    assert audit_text("yüzde iki nokta sıfır sekiz", package)
