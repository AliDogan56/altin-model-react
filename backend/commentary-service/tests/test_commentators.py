"""Yorumcu gözcüsü: liste, RSS penceresi, tekilleştirme, özet (sahte LLM), saklama/bayatlık, masa kaydı, atıf denetimi, parmak izi."""
import datetime as dt
import json
from email.utils import format_datetime

import pytest

from app.services import commentator_service as cs
from app.services.llm_config import LlmSettings, ProviderConfig, RoleConfig
from app.services.run_planner import input_fingerprint, inputs_changed

NOW = dt.datetime(2026, 9, 16, 9, 0, tzinfo=dt.UTC)
MEMIS = {"ad": "İslam Memiş", "sorgu": "İslam Memiş altın"}


def _rss(rows):
    items = "".join(f"<item><title>{t} - {k}</title><link>https://x/{i}</link><pubDate>{format_datetime(NOW - dt.timedelta(hours=h))}</pubDate></item>"
                    for i, (t, k, h) in enumerate(rows))
    return f'<?xml version="1.0"?><rss><channel>{items}</channel></rss>'


def test_load_commentators_reads_toml(tmp_path):
    path = tmp_path / "y.toml"
    path.write_text('[[yorumcu]]\nad = "İslam Memiş"\nsorgu = "İslam Memiş altın"\n[[yorumcu]]\nad = "  "\n[[yorumcu]]\nad = "X"\n')
    assert cs.load_commentators(path) == [MEMIS, {"ad": "X", "sorgu": "X"}]
    assert cs.load_commentators(tmp_path / "yok.toml") == []


def test_dedupe_collapses_syndicated_titles_and_keeps_newest():
    items = [
        {"baslik": "İslam Memiş çarşamba günü için saat verdi: altın ve gümüşte kırılım olacak", "zaman_utc": "2026-09-16T08:00:00+00:00"},
        {"baslik": "İSLAM MEMİŞ ÇARŞAMBA GÜNÜ İÇİN SAAT VERDİ! ALTIN VE GÜMÜŞTE KIRILIM OLACAK", "zaman_utc": "2026-09-16T07:00:00+00:00"},
        {"baslik": "İslam Memiş'ten altın kritiği: sakın bozmayın", "zaman_utc": "2026-09-16T06:00:00+00:00"},
    ]
    kept = cs.dedupe(items)
    assert [k["zaman_utc"] for k in kept] == ["2026-09-16T08:00:00+00:00", "2026-09-16T06:00:00+00:00"]


def test_fetch_statements_filters_window_dedupes_and_caps():
    xml = _rss([("İslam Memiş çarşambaya dikkat dedi", "A Gazete", 5), ("İslam Memiş çarşambaya dikkat dedi", "B Gazete", 6),
                ("İslam Memiş altın için tarih verdi", "C", 20), ("Eski haber: İslam Memiş yaz aylarında altın", "D", 80)])
    rows = cs.fetch_statements([MEMIS], hours=48, fetch=lambda url, timeout=20: xml, now=NOW)
    assert [r["kaynak"] for r in rows] == ["A Gazete", "C"]          # kopya ve 80 saatlik haber düştü
    assert rows[0]["ad"] == "İslam Memiş" and rows[0]["saat_turkiye"] == "16.09 07:00" and rows[0]["url"] == "https://x/0"
    assert cs.fetch_statements([MEMIS], hours=48, fetch=lambda url, timeout=20: (_ for _ in ()).throw(OSError("ağ yok")), now=NOW) == []


def _mock_llm():
    return LlmSettings({"m": ProviderConfig("m", "mock")}, {"commentator_scout": RoleConfig(name="commentator_scout", provider="m", model="mock-1")}, 0, "x")


def test_build_digest_uses_llm_only_with_statements_and_keeps_listed_names_only(monkeypatch):
    empty = cs.build_digest(_mock_llm(), [MEMIS], [], now=NOW)
    assert empty["yorumcular"] == [] and empty["usage"] is None and empty["uretildi_utc"] == "2026-09-16T09:00:00+00:00"

    statements = [{"ad": "İslam Memiş", "baslik": "b1", "kaynak": "A", "url": "u", "zaman_utc": "2026-09-16T08:00:00+00:00", "saat_turkiye": "16.09 11:00"}]
    fake = {"yorumcular": [
        {"ad": "İslam Memiş", "yon": "temkinli", "vade": "bu hafta", "ana_iddia": " ".join(["kelime"] * 60), "sayisal_hedefler": ["çarşamba 21:00"],
         "dayanak": {"baslik": "b1", "kaynak": "A", "saat_turkiye": "16.09 11:00"}, "haber_sayisi": 99},
        {"ad": "Başka Uzman", "yon": "yukselis", "vade": "", "ana_iddia": "x", "sayisal_hedefler": [], "dayanak": {}, "haber_sayisi": 1},
        {"ad": "İslam Memiş", "yon": "saçma", "vade": "", "ana_iddia": "y", "sayisal_hedefler": [], "dayanak": {}, "haber_sayisi": 1}],
        "ozet_cumle": "Sesler temkinli."}
    monkeypatch.setattr(cs, "ask", lambda *a, **k: (json.dumps(fake, ensure_ascii=False), type("U", (), {"as_dict": lambda self: {"in": 1}})(), "m/mock"))
    digest = cs.build_digest(_mock_llm(), [MEMIS], statements, now=NOW)
    names = [r["ad"] for r in digest["yorumcular"]]
    assert names == ["İslam Memiş", "İslam Memiş"] and "Başka Uzman" not in names   # liste dışı ad düştü
    first = digest["yorumcular"][0]
    assert len(first["ana_iddia"].split()) == cs.MAX_CLAIM_WORDS and first["haber_sayisi"] == 1   # sayım LLM'den değil başlıklardan
    assert digest["yorumcular"][1]["yon"] == "belirsiz" and digest["ozet_cumle"] == "Sesler temkinli." and digest["model"] == "m/mock"


def test_save_read_and_staleness(tmp_path):
    digest = {"uretildi_utc": NOW.isoformat(), "pencere_saat": 48, "yorumcular": [], "ozet_cumle": "", "kaynaklar": []}
    cs.save_digest(digest, tmp_path)
    assert cs.read_digest(tmp_path, now=NOW + dt.timedelta(hours=23)) == digest
    assert cs.read_digest(tmp_path, now=NOW + dt.timedelta(hours=25)) is None       # bayat
    assert cs.read_digest(tmp_path / "yok", now=NOW) is None


def test_for_desk_is_anonymous_and_drops_numeric_targets():
    configured = [MEMIS, {"ad": "X", "sorgu": "X"}, {"ad": "Y", "sorgu": "Y"}]
    digest = {"yorumcular": [
        {"ad": "Y", "yon": "yukselis", "vade": "kısa vade", "ana_iddia": "Al.", "sayisal_hedefler": [], "dayanak": {"baslik": "b", "kaynak": "B", "saat_turkiye": "16.09 12:00"}, "haber_sayisi": 1},
        {"ad": "İslam Memiş", "yon": "temkinli", "vade": "bu hafta", "ana_iddia": "Karar öncesi bekle.",
         "sayisal_hedefler": ["gram 10 bin"], "dayanak": {"baslik": "b", "kaynak": "A", "saat_turkiye": "16.09 11:00"}, "haber_sayisi": 3}]}
    rows = cs.for_desk(digest, configured)
    assert rows == [{"etiket": "Yorumcu 1", "yon": "temkinli", "vade": "bu hafta", "ana_iddia": "Karar öncesi bekle.", "dayanak": "A 16.09 11:00", "haber_sayisi": 3},
                    {"etiket": "Yorumcu 3", "yon": "yukselis", "vade": "kısa vade", "ana_iddia": "Al.", "dayanak": "B 16.09 12:00", "haber_sayisi": 1}]
    assert all("ad" not in r and "sayisal_hedefler" not in r for r in rows) and cs.for_desk(None, configured) == []
    assert cs.desk_summary(rows, 3) == {"izlenen": 3, "konusan": 2, "yon_dagilimi": {"temkinli": 1, "yukselis": 1}, "baskin_yon": "karisik"}
    assert cs.desk_summary(rows[:1], 3)["baskin_yon"] == "temkinli" and cs.desk_summary([], 3)["baskin_yon"] is None


def test_names_must_not_appear_in_text():
    assert cs.attribution_problems("Haberlere yansıyan tanınmış yorumcular temkinli.", [], ["İslam Memiş", "X"]) == []
    assert cs.attribution_problems("Haberlere göre İslam Memiş temkinli.", [], ["İslam Memiş", "X"]) == ["yorumcu adı metinde geçmemeli: İslam Memiş (yorumcular adsız, toplu anılır)"]


def test_fingerprint_tracks_commentator_view():
    pkg = {"takvim": {}, "faiz_beklentisi": {}, "enflasyon": {}, "pozisyon": {}, "makro_son": {}}
    a = input_fingerprint(pkg, [], [{"etiket": "Yorumcu 1", "yon": "temkinli", "ana_iddia": "bekle"}])
    b = input_fingerprint(pkg, [], [{"etiket": "Yorumcu 1", "yon": "yukselis", "ana_iddia": "al"}])
    assert inputs_changed(a, a) == (False, "girdiler aynı")
    assert inputs_changed(a, b) == (True, "yorumcular değişti")
    assert inputs_changed(a, input_fingerprint(pkg, [], [])) == (True, "yorumcular değişti")


@pytest.mark.parametrize("sorgu", ["İslam Memiş altın"])
def test_rss_url_is_turkish_google_news(sorgu):
    url = cs.rss_url(sorgu)
    assert url.startswith("https://news.google.com/rss/search?q=") and "hl=tr&gl=TR&ceid=TR:tr" in url and " " not in url


def test_strip_numbers_keeps_sentence_readable():
    assert cs.strip_numbers("Fed sürpriz yaparsa ons altın 4.400 dolara çıkabilir.") == "Fed sürpriz yaparsa ons altın … dolara çıkabilir."
    assert cs.strip_numbers("gram altın 10 bin lira, yüzde 5 düşüş") == "gram altın … lira, … düşüş"
    assert cs.strip_numbers("") == "" and cs.strip_numbers("sayı yok") == "sayı yok"
