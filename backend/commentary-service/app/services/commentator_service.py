"""Yorumcu gözcüsü (2026-09-16).

Türkiye'deki tanınmış altın yorumcularının son 72 saatte (`COMMENTATOR_WINDOW_HOURS`) **habere yansıyan** sözlerini derler ve tek LLM
çağrısıyla yön / vade / ana iddia özetine çevirir; sonuç `latest/yorumcular.json`. Masa (baş analist ve
anlatıcı) hazır özeti okur, kendi görüşünü ona göre değiştirmez; okuyucuya "piyasadaki sesler"i verir.

Neden haber, video değil: yorumcuların TV ve YouTube sözleri saatler içinde onlarca habere dönüşüyor
(ölçüldü 2026-09-15: İslam Memiş 48 saatte 13 başlık). YouTube altyazısı bulut IP'lerinden engelli,
Gemini'ye video vermek tur başına 90–200 bin token. Haber yolu sıfır ek altyapı: mevcut RSS ayrıştırıcı.

Üretim zincirine girmez: iş döngüsü `COMMENTATOR_REFRESH_MINUTES` aralığıyla tazeler (varsayılan 6 saat),
üretim anında yalnız disk okunur. Aynı söz on siteye dağılır; başlıklar kelime kümesi benzerliğiyle
tekilleştirilir. Yorumcunun sayısal hedefleri kayda girer ama masaya **verilmez**: masanın kuralı
"sayılar yalnız veri paketinden gelir" ve denetim pakette olmayan sayıyı zaten reddeder.

**Adsız aktarım (kullanıcı kararı, 2026-09-16):** tek ismi öne çıkarmamak için masa yorumcuları adla değil
toplu olarak anar ("haberlere yansıyan tanınmış yorumcular"). Kayıtta ad durur (tekilleştirme, ileride karne),
masaya giden görünüm adsızdır (`Yorumcu 1..n` etiketi + yön dağılımı) ve denetim metinde listedeki bir ad
geçerse düzeltme ister.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import tomllib
from pathlib import Path

from ..config import settings
from ..market_constants import LATEST_DIR
from .http_client import get_text
from .llm_gateway import ask, parse_json
from .news_service import parse_rss

DIGEST_FILE = "yorumcular.json"
DIGEST_MAX_AGE_HOURS = 24
SIMILARITY = 0.6            # Jaccard: aynı sözün başka bir sitedeki başlığı
PER_NAME = 8
YON = ("yukselis", "dusus", "temkinli", "karisik", "belirsiz")
MAX_CLAIM_WORDS = 45

YORUMCU_SCHEMA = {
    "type": "object",
    "properties": {
        "yorumcular": {"type": "array", "items": {"type": "object", "properties": {
            "ad": {"type": "string"}, "yon": {"type": "string", "enum": list(YON)}, "vade": {"type": "string"},
            "ana_iddia": {"type": "string"}, "sayisal_hedefler": {"type": "array", "items": {"type": "string"}},
            "dayanak": {"type": "object", "properties": {"baslik": {"type": "string"}, "kaynak": {"type": "string"}, "saat_turkiye": {"type": "string"}},
                        "required": ["baslik", "kaynak", "saat_turkiye"], "additionalProperties": False},
            "haber_sayisi": {"type": "integer"}},
            "required": ["ad", "yon", "vade", "ana_iddia", "sayisal_hedefler", "dayanak", "haber_sayisi"], "additionalProperties": False}},
        "ozet_cumle": {"type": "string"},
    },
    "required": ["yorumcular", "ozet_cumle"], "additionalProperties": False,
}

_WORD_RX = re.compile(r"[^\w\s]", re.UNICODE)
# Sayısal hedef (4.400, 10 bin, yüzde 5): masaya giden özetten çıkarılır, yalnız `sayisal_hedefler` kaydında kalır.
_NUMBER_RX = re.compile(r"(?:yüzde\s*)?\d[\d.,]*(?:\s*(?:bin|milyon|milyar))?", re.IGNORECASE)


def strip_numbers(text: str) -> str:
    """'ons altın 4.400 dolara çıkabilir' → 'ons altın … dolara çıkabilir': sayı masaya gitmez, boşluk okunur kalır."""
    return re.sub(r"\s{2,}", " ", _NUMBER_RX.sub("…", text or "")).strip()


def load_commentators(path: Path | None = None) -> list[dict]:
    """`yorumcular.toml` → [{ad, sorgu}]; dosya yoksa boş liste (gözcü kapalı)."""
    path = Path(path or settings.commentators_path)
    if not path.exists():
        return []
    with open(path, "rb") as source:
        rows = tomllib.load(source).get("yorumcu", [])
    return [{"ad": str(r.get("ad", "")).strip(), "sorgu": str(r.get("sorgu") or r.get("ad", "")).strip()} for r in rows if str(r.get("ad", "")).strip()]


def rss_url(sorgu: str) -> str:
    from urllib.parse import quote
    return f"https://news.google.com/rss/search?q={quote(sorgu)}&hl=tr&gl=TR&ceid=TR:tr"


def _lower_tr(text: str) -> str:
    """Türkçe küçültme: Python `lower()` 'İ'yi 'i̇' (i + birleşik nokta) yapar, 'VERDİ' ile 'verdi' eşleşmez."""
    return text.replace("İ", "i").replace("I", "ı").lower()


def _words(title: str) -> set[str]:
    return {w for w in _WORD_RX.sub(" ", _lower_tr(title)).split() if len(w) > 2}


def dedupe(items: list[dict], threshold: float = SIMILARITY) -> list[dict]:
    """Aynı sözün farklı sitelerdeki başlıkları tek kayda iner; en yeni kalır. Kelime kümesi Jaccard benzerliği."""
    kept: list[tuple[set[str], dict]] = []
    for item in sorted(items, key=lambda h: h.get("zaman_utc") or "", reverse=True):
        words = _words(item.get("baslik") or "")
        if not words:
            continue
        if any(len(words & w) / len(words | w) >= threshold for w, _ in kept):
            continue
        kept.append((words, item))
    return [item for _, item in kept]


def _turkiye(iso_utc: str | None) -> str:
    try:
        return dt.datetime.fromisoformat(iso_utc).astimezone(dt.timezone(dt.timedelta(hours=3))).strftime("%d.%m %H:%M")
    except (TypeError, ValueError):
        return ""


def fetch_statements(commentators: list[dict], hours: int | None = None, per_name: int = PER_NAME, fetch=get_text,
                     now: dt.datetime | None = None) -> list[dict]:
    """Her yorumcu için pencere içindeki, tekilleştirilmiş haber başlıkları (en yeni önce, `per_name` ile sınırlı)."""
    now = now or dt.datetime.now(dt.UTC)
    threshold = now - dt.timedelta(hours=hours or settings.commentator_window_hours)
    out: list[dict] = []
    for person in commentators:
        try:
            rows = parse_rss(fetch(rss_url(person["sorgu"]), timeout=20), "tr")
        except Exception:  # noqa: BLE001
            continue
        fresh = []
        for row in rows:
            try:
                if dt.datetime.fromisoformat(row["zaman_utc"]) < threshold:
                    continue
            except (TypeError, ValueError):
                continue
            fresh.append(row)
        for row in dedupe(fresh)[:per_name]:
            out.append({"ad": person["ad"], "baslik": row["baslik"][:160], "kaynak": row.get("kaynak") or "", "url": row.get("url") or "",
                        "zaman_utc": row["zaman_utc"], "saat_turkiye": _turkiye(row["zaman_utc"])})
    return out


def _sanitize(record: dict, allowed: set[str], counts: dict[str, int]) -> dict | None:
    ad = str(record.get("ad") or "").strip()
    if ad not in allowed:
        return None
    words = str(record.get("ana_iddia") or "").split()
    dayanak = record.get("dayanak") if isinstance(record.get("dayanak"), dict) else {}
    return {"ad": ad, "yon": record.get("yon") if record.get("yon") in YON else "belirsiz", "vade": str(record.get("vade") or "")[:60],
            "ana_iddia": strip_numbers(" ".join(words[:MAX_CLAIM_WORDS])),
            "sayisal_hedefler": [str(x)[:80] for x in (record.get("sayisal_hedefler") or []) if str(x).strip()][:6],
            "dayanak": {k: str(dayanak.get(k) or "")[:160] for k in ("baslik", "kaynak", "saat_turkiye")},
            "haber_sayisi": counts.get(ad, 0)}


def build_digest(llm, commentators: list[dict], statements: list[dict], now: dt.datetime | None = None) -> dict:
    """Başlıklardan tek LLM çağrısıyla özet; başlık yoksa çağrı yapılmaz. Yalnız izleme listesindeki adlar kalır."""
    from .commentary_pipeline import role_prompt   # döngüsel içe aktarma: pipeline bu modülü okur
    now = now or dt.datetime.now(dt.UTC)
    counts: dict[str, int] = {}
    for s in statements:
        counts[s["ad"]] = counts.get(s["ad"], 0) + 1
    digest = {"uretildi_utc": now.replace(microsecond=0).isoformat(), "pencere_saat": settings.commentator_window_hours,
              "yorumcular": [], "ozet_cumle": "", "kaynaklar": [{k: s[k] for k in ("ad", "baslik", "kaynak", "url", "saat_turkiye")} for s in statements],
              "usage": None, "model": None}
    if not statements:
        return digest
    by_name = {p["ad"]: [{"baslik": s["baslik"], "kaynak": s["kaynak"], "saat_turkiye": s["saat_turkiye"]} for s in statements if s["ad"] == p["ad"]]
               for p in commentators}
    user = ("İzleme listesi: " + ", ".join(p["ad"] for p in commentators) + "\n\nYorumcu başına son " + str(settings.commentator_window_hours)
            + " saatin haber başlıkları (kaynak, Türkiye saati):\n" + json.dumps({k: v for k, v in by_name.items() if v}, ensure_ascii=False)
            + "\n\nRol tanımındaki JSON'u döndür.")
    text, used, model = ask(llm, "commentator_scout", role_prompt("commentator_scout"), user, YORUMCU_SCHEMA)
    parsed = parse_json(text)
    allowed = {p["ad"] for p in commentators}
    digest["yorumcular"] = [r for r in (_sanitize(x, allowed, counts) for x in parsed.get("yorumcular") or []) if r]
    digest["ozet_cumle"] = strip_numbers(str(parsed.get("ozet_cumle") or "")[:240])
    digest["usage"], digest["model"] = used.as_dict(), model
    return digest


def save_digest(digest: dict, directory: Path | None = None) -> Path:
    directory = Path(directory or LATEST_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / DIGEST_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(digest, ensure_ascii=False, indent=2))
    os.replace(tmp, path)
    return path


def read_digest(directory: Path | None = None, max_age_hours: int = DIGEST_MAX_AGE_HOURS, now: dt.datetime | None = None) -> dict | None:
    """Diskteki özet; yoksa ya da `max_age_hours`'tan eskiyse None (bayat söz masaya gitmez)."""
    path = Path(directory or LATEST_DIR) / DIGEST_FILE
    try:
        digest = json.loads(path.read_text())
        made = dt.datetime.fromisoformat(digest["uretildi_utc"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    now = now or dt.datetime.now(dt.UTC)
    if made.tzinfo is None:
        made = made.replace(tzinfo=dt.UTC)
    return digest if (now - made) <= dt.timedelta(hours=max_age_hours) else None


def for_desk(digest: dict | None, configured: list[dict] | None = None) -> list[dict]:
    """Masaya giden kompakt, **adsız** kayıtlar: etiket (`Yorumcu 1..n`, izleme listesi sırasıyla, sabit), yön, vade,
    ana iddia, dayanak saati, haber sayısı. Ad ve sayısal hedef yok."""
    if not digest:
        return []
    order = [p["ad"] for p in (configured if configured is not None else load_commentators())]
    label = lambda ad: f"Yorumcu {order.index(ad) + 1}" if ad in order else "Yorumcu"  # noqa: E731
    rows = [{"etiket": label(r["ad"]), "yon": r["yon"], "vade": r["vade"], "ana_iddia": r["ana_iddia"],
             "dayanak": f"{r['dayanak'].get('kaynak', '')} {r['dayanak'].get('saat_turkiye', '')}".strip(), "haber_sayisi": r["haber_sayisi"]}
            for r in digest.get("yorumcular") or []]
    return sorted(rows, key=lambda r: r["etiket"])


def desk_summary(rows: list[dict], watched: int) -> dict:
    """Baş analistin tek cümlede kullanacağı sayım: izlenen, bu pencerede konuşan, yön dağılımı, baskın yön."""
    dist: dict[str, int] = {}
    for r in rows:
        dist[r["yon"]] = dist.get(r["yon"], 0) + 1
    dominant = max(dist, key=lambda k: (dist[k], k)) if dist else None
    return {"izlenen": watched, "konusan": len(rows), "yon_dagilimi": dist,
            "baskin_yon": dominant if dominant and dist[dominant] * 2 > len(rows) else ("karisik" if rows else None)}


def attribution_problems(text: str, desk_rows: list[dict], configured_names: list[str]) -> list[str]:
    """Adsız aktarım: metinde izleme listesindeki bir ad geçiyorsa düzeltme ister (yorumcular toplu anılır)."""
    del desk_rows  # imza uyumu; karar yalnız ada bakar
    return [f"yorumcu adı metinde geçmemeli: {name} (yorumcular adsız, toplu anılır)" for name in configured_names if name and name in text]


def refresh(llm, now: dt.datetime | None = None, fetch=get_text) -> dict:
    """Listeyi oku → başlıkları çek → özetle → kaydet. Liste boşsa boş özet yazar (masa 'veri yok' görür)."""
    commentators = load_commentators()
    statements = fetch_statements(commentators, fetch=fetch, now=now) if commentators else []
    digest = build_digest(llm, commentators, statements, now=now)
    save_digest(digest)
    return digest
