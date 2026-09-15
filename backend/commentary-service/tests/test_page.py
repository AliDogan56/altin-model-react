"""`/yorum` sayfa parçaları: kaçırma, tarih, açıklama kısaltma, yorum yokken noindex, uçlar."""
import datetime as dt
import json

from fastapi.testclient import TestClient

from app.main import app
from app.services import commentary_page as page
from app.services.commentary_store import commentary_store

ITEM = {
    "version": "20260915T125439Z", "as_of": "2026-09-15", "generated_at": "2026-09-15T12:54:39+00:00",
    "run_mode": "full", "trigger": {"reason": "ilk"},
    "live": {"price": 4292.75, "source": "PAXG-USD", "time_utc": "2026-09-15T12:50:00+00:00"},
    "official_fix": {"date": "2026-09-14", "price": 4267.1},
    "title": "Ons AI yorumu", "headline": "Ons altın <faiz> kararı öncesinde 4.292,75 dolar seviyesinde \"baskı\" altında",
    "summary": " ".join(["Piyasa temkinli."] * 30),
    "sections": [{"id": "bugun", "title": "Bugün ne oldu", "text": "Fiyat 4.292 dolar. </script> denemesi"},
                 {"id": "kapanis", "title": "Kapanış", "text": "Sakin."}],
    "usage": {"gemini": 1}, "durations_seconds": {"llm": 50}, "disclaimer": "Yatırım tavsiyesi değildir.", "narration": None,
}


def test_turkish_date_and_time_in_istanbul():
    assert page.tarih_tr("2026-09-15T12:54:39+00:00") == "15 Eylül 2026"
    assert page.tarih_saat_tr("2026-09-15T22:30:00+00:00") == "16 Eylül 2026, 01:30"   # gün Türkiye saatinde döner
    assert page.tarih_tr("bozuk") == "" and page.tarih_tr(None) == ""


def test_description_is_cut_at_word_boundary():
    desc = page.page_description(ITEM)
    assert len(desc) <= page.DESCRIPTION_MAX and desc.endswith("…") and not desc.endswith(" …")
    assert page.page_description({"summary": "Kısa özet."}) == "Kısa özet."
    assert "yeniden yazılır" in page.page_description(None)


def test_body_escapes_llm_text_and_embeds_json():
    body = page.page_body(ITEM)
    assert "&lt;faiz&gt;" in body and "&quot;baskı&quot;" in body and "<faiz>" not in body
    assert "&lt;/script&gt; denemesi" in body
    assert "<h1>" in body and body.count("<h2>") == 2 and "Ons altın yorumu · 15 Eylül 2026, 15:54" in body
    assert "spot izleyen seri" in body and "PAXG" not in body.split("<script")[0]   # kaynak kodu metinde yok
    assert "4.292,75 $" in body and "4.267,10 $" in body
    start = body.index(f'id="{page.EMBED_ID}">') + len(f'id="{page.EMBED_ID}">')
    raw = body[start: body.index("</script>", start)]
    assert "</script" not in raw and "\\u003c" in raw
    embedded = json.loads(raw)
    assert embedded["version"] == ITEM["version"] and "usage" not in embedded and "durations_seconds" not in embedded
    assert embedded["sections"][0]["text"] == ITEM["sections"][0]["text"]


def test_head_carries_description_dates_and_article_schema():
    head = page.page_head(ITEM)
    assert 'name="description"' in head and 'property="article:modified_time" content="2026-09-15T12:54:39+00:00"' in head
    assert "noindex" not in head
    ld = json.loads(head.split('<script type="application/ld+json">')[1].split("</script>")[0])
    article = ld["@graph"][0]
    assert article["@type"] == "Article" and article["headline"] == ITEM["headline"]
    assert article["dateModified"] == ITEM["generated_at"] and article["mainEntityOfPage"].endswith("/yorum")
    assert ld["@graph"][1]["@type"] == "BreadcrumbList"


def test_no_commentary_means_noindex_and_pending_body():
    head, body = page.page_head(None), page.page_body(None)
    assert 'content="noindex,follow"' in head and "ld+json" not in head
    assert page.PENDING_TITLE in body and page.EMBED_ID not in body


def test_lastmod_is_w3c_datetime():
    assert page.lastmod(ITEM) == "2026-09-15T15:54:39+03:00"
    fixed = dt.datetime(2026, 9, 15, 10, 0, tzinfo=dt.UTC)
    assert page.lastmod(None, now=fixed) == "2026-09-15T10:00:00+00:00"


def test_endpoints_return_200_with_and_without_commentary(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(commentary_store, "latest", lambda: None)
    r = client.get("/v1/commentary/latest/page/head")
    assert r.status_code == 200 and "noindex" in r.text and r.headers["content-type"].startswith("text/html")
    assert client.get("/v1/commentary/latest/page/body").status_code == 200
    assert client.get("/v1/commentary/latest/page/lastmod").text.count("T") == 1

    monkeypatch.setattr(commentary_store, "latest", lambda: dict(ITEM))
    body = client.get("/v1/commentary/latest/page/body").text
    assert "<h1>" in body and page.EMBED_ID in body
    assert client.get("/v1/commentary/latest/page/lastmod").text == "2026-09-15T15:54:39+03:00"
