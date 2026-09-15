"""
`/yorum` sayfasının sunucu tarafı parçaları (2026-09-15).

Yorum metni tarayıcıda bir pencerede gösteriliyordu; Google için bir URL'i yoktu.
Web konteynerinin nginx'i `/yorum` isteğinde derlemede üretilmiş sayfa kabuğunu
okur ve iki noktaya SSI ile buradaki parçaları ekler: `<head>` içine açıklama,
paylaşım etiketleri ve Article şeması; gövdeye makalenin kendisi ve React'in
hidrasyonda eşzamanlı okuyacağı JSON. Böylece arama motoru JavaScript çalıştırmadan
**o anki** metni görür; sayfa kabuğu statik kalır, içerik her istekte diskten gelir.

Kurallar:
- LLM metni HTML'e **kaçırılarak** girer (`html.escape`); JSON gömüsünde `<` `\\u003c` olur.
- Yorum yoksa parçalar yine 200 döner (SSI hata metni basmasın) ama sayfa `noindex` alır;
  "hazırlanıyor" hâli dizine girmemeli.
- Başlık sabit ve kabukta (`Ons Altın Yorumu Bugün`); tarih görünür üst yazıda ve
  `dateModified` içinde. Servis düşerse sayfa başlıksız kalmaz, yalnız açıklaması eksilir.
"""
from __future__ import annotations

import datetime as dt
import html
import json

from .commentary_pipeline import plain_source

SITE_URL = "https://onsaltinanaliz.com"
PAGE_PATH = "/yorum"
PAGE_TITLE = "Ons Altın Yorumu Bugün"
SITE_NAME = "Ons Altın Analiz"
GUIDE_PATH = "/rehber/ons-altin-yorum"
DESCRIPTION_MAX = 155
EMBED_ID = "yorum-verisi"
AYLAR = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")
TR = dt.timezone(dt.timedelta(hours=3))
_OMIT_FROM_EMBED = ("usage", "durations_seconds")

DISCLOSURE = ("Bu metni beş rolden oluşan bir yapay zekâ masası yazdı: teknik analist, takvim ve haber gözcüsü, "
              "makro analist, baş analist ve anlatıcı. Metindeki her sayı o an ölçülmüş veri paketinden gelir ve "
              "yayımlanmadan önce paketle karşılaştırılır. Masa fiyatı beş dakikada bir kontrol eder; fiyat yarım "
              "yüzdeden fazla oynadıysa ya da dört saat geçtiyse metni yeniden yazar.")
PENDING_TITLE = "Bugünkü ons altın yorumu hazırlanıyor"
PENDING_TEXT = ("Masa ilk yorumu yazıyor: fiyat verisi toplanıyor ve beş uzman rolü sırayla çalışıyor. "
                "Metin hazır olunca bu sayfada görünecek.")


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _tr_time(iso_utc: str | None) -> dt.datetime | None:
    if not iso_utc:
        return None
    try:
        parsed = dt.datetime.fromisoformat(iso_utc)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(TR)


def tarih_tr(iso_utc: str | None) -> str:
    """'2026-09-15T12:54:39+00:00' → '15 Eylül 2026' (Türkiye saati)."""
    t = _tr_time(iso_utc)
    return f"{t.day} {AYLAR[t.month - 1]} {t.year}" if t else ""


def tarih_saat_tr(iso_utc: str | None) -> str:
    t = _tr_time(iso_utc)
    return f"{t.day} {AYLAR[t.month - 1]} {t.year}, {t:%H:%M}" if t else ""


def _money(value: object) -> str:
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " $"
    except (TypeError, ValueError):
        return "—"


def page_description(item: dict | None) -> str:
    """Özet, kelime sınırında 155 karaktere kısaltılır; sonuç sonuçta gösterilen snippet bu."""
    if not item:
        return "Yapay zekâ masasının günlük ons altın yorumu; fiyat oynadıkça yeniden yazılır, sayıları veri paketiyle denetlenir."
    text = " ".join(str(item.get("summary") or "").split())
    if len(text) <= DESCRIPTION_MAX:
        return text
    cut = text[: DESCRIPTION_MAX - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(",.;:") + "…"


def lastmod(item: dict | None, now: dt.datetime | None = None) -> str:
    """Sitemap `<lastmod>` değeri (W3C tarih-saat). Yorum yoksa şimdiki zaman."""
    stamp = _tr_time(item.get("generated_at")) if item else None
    if stamp is None:
        stamp = (now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC)
    return stamp.isoformat(timespec="seconds")


def json_embed(item: dict) -> str:
    """React'in hidrasyonda eşzamanlı okuduğu gömü; `/latest` şemasıyla birebir, ölçüm alanları hariç."""
    slim = {k: v for k, v in item.items() if k not in _OMIT_FROM_EMBED}
    body = json.dumps(slim, ensure_ascii=False).replace("<", "\\u003c")
    return f'<script type="application/json" id="{EMBED_ID}">{body}</script>'


def json_ld(item: dict) -> str:
    url = f"{SITE_URL}{PAGE_PATH}"
    org = {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL}
    graph = [
        {"@type": "Article", "headline": item.get("headline"), "description": page_description(item),
         "mainEntityOfPage": url, "url": url, "image": f"{SITE_URL}/social-preview-v1.png",
         "author": org, "publisher": org,
         "datePublished": item.get("generated_at"), "dateModified": item.get("generated_at"),
         "inLanguage": "tr-TR", "articleSection": "Ons Altın Yorumu", "keywords": "ons altın yorum, ons altın yorumu bugün, altın analizi",
         "isAccessibleForFree": True},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Ana Sayfa", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": PAGE_TITLE, "item": url}]},
    ]
    payload = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("</script", "<\\/script")
    return f'<script type="application/ld+json">{payload}</script>'


def page_head(item: dict | None) -> str:
    """`<head>` parçası: açıklama, paylaşım etiketleri, tarih ve şema. Başlık ve canonical kabukta."""
    title = f"{PAGE_TITLE} | {SITE_NAME}"
    desc = page_description(item)
    url = f"{SITE_URL}{PAGE_PATH}"
    tags = [
        f'<meta name="description" content="{_e(desc)}" />',
        '<meta property="og:type" content="article" />',
        f'<meta property="og:title" content="{_e(title)}" />',
        f'<meta property="og:description" content="{_e(desc)}" />',
        f'<meta property="og:url" content="{url}" />',
        f'<meta name="twitter:title" content="{_e(title)}" />',
        f'<meta name="twitter:description" content="{_e(desc)}" />',
    ]
    if not item:
        tags.append('<meta name="robots" content="noindex,follow" />')
        return "\n    ".join(tags)
    stamp = item.get("generated_at") or ""
    tags += [
        f'<meta property="article:published_time" content="{_e(stamp)}" />',
        f'<meta property="article:modified_time" content="{_e(stamp)}" />',
        '<meta property="article:section" content="Ons Altın Yorumu" />',
        json_ld(item),
    ]
    return "\n    ".join(tags)


def _facts(item: dict) -> str:
    rows = []
    live = item.get("live") or {}
    if live.get("price") is not None:
        source = plain_source(live.get("source")) or "canlı seri"
        rows.append(f"<div><dt>Yorum yazılırken fiyat</dt><dd>{_e(_money(live['price']))}</dd><small>{_e(source)}</small></div>")
    fix = item.get("official_fix") or {}
    if fix.get("price") is not None:
        rows.append(f"<div><dt>Resmi fiks</dt><dd>{_e(_money(fix['price']))}</dd><small>{_e(fix.get('date') or '')}</small></div>")
    stamp = item.get("generated_at") or ""
    rows.append(f'<div><dt>Yazıldı</dt><dd><time datetime="{_e(stamp)}">{_e(tarih_saat_tr(stamp))}</time></dd><small>Türkiye saati</small></div>')
    return f'<dl class="yorum-facts">{"".join(rows)}</dl>'


def page_body(item: dict | None) -> str:
    """Gövde parçası: makale + JSON gömüsü. Kabuk (`main.seo-prerender`, içerik yolu, altbilgi) derlemede basılır."""
    if not item:
        return (f"<article><header><h1>{PENDING_TITLE}</h1><p>{PENDING_TEXT}</p></header>"
                f'<p><a href="/">Canlı panele dön</a> · <a href="{GUIDE_PATH}">Ons altın yorumu nasıl okunur</a></p></article>')
    stamp = item.get("generated_at") or ""
    sections = "".join(
        f"<section><h2>{_e(s.get('title') or '')}</h2><p>{_e(s.get('text') or '')}</p></section>"
        for s in item.get("sections") or [])
    return (
        "<article>"
        f"<header><p>Ons altın yorumu · {_e(tarih_saat_tr(stamp))}</p>"
        f"<h1>{_e(item.get('headline') or '')}</h1>"
        f"<p>{_e(item.get('summary') or '')}</p></header>"
        f"{_facts(item)}"
        f"<p><small>{DISCLOSURE}</small></p>"
        f"{sections}"
        f"<p><small>{_e(item.get('disclaimer') or '')}</small></p>"
        f'<p><a href="/">Canlı panelde aç</a> · <a href="{GUIDE_PATH}">Ons altın yorumu nasıl okunur</a></p>'
        f'<p><small>Son güncelleme: <time datetime="{_e(stamp)}">{_e(tarih_saat_tr(stamp))}</time></small></p>'
        "</article>"
        f"{json_embed(item)}"
    )
