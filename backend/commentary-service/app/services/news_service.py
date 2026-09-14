"""Betikle haber başlığı: Google News RSS (anahtarsız). Hızlı üretici web araması yapmaz, bu listeyi okur."""
from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from .http_client import get_text

SORGULAR = [
    ("https://news.google.com/rss/search?q=gold+price&hl=en-US&gl=US&ceid=US:en", "en"),
    ("https://news.google.com/rss/search?q=ons+alt%C4%B1n&hl=tr&gl=TR&ceid=TR:tr", "tr"),
]


def parse_rss(xml_text: str, dil: str) -> list[dict]:
    out = []
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        src = item.find("source")
        kaynak = (src.text if src is not None else "").strip()
        pub = item.findtext("pubDate") or ""
        try:
            zaman = parsedate_to_datetime(pub).astimezone(dt.UTC).replace(microsecond=0).isoformat()
        except Exception:  # noqa: BLE001
            zaman = pub
        if " - " in title and not kaynak:
            title, kaynak = title.rsplit(" - ", 1)
        out.append({"baslik": title, "kaynak": kaynak, "zaman_utc": zaman, "url": (item.findtext("link") or "").strip(), "dil": dil})
    return out


def son_haberler(saat: int = 24, en_fazla: int = 12) -> list[dict]:
    esik = dt.datetime.now(dt.UTC) - dt.timedelta(hours=saat)
    hepsi: list[dict] = []
    for url, dil in SORGULAR:
        try:
            hepsi += parse_rss(get_text(url, timeout=20), dil)
        except Exception as exc:  # noqa: BLE001
            hepsi.append({"baslik": f"[RSS alınamadı: {exc}]", "kaynak": "", "zaman_utc": "", "url": "", "dil": dil})
    def taze(h):
        try:
            return dt.datetime.fromisoformat(h["zaman_utc"]) >= esik
        except Exception:  # noqa: BLE001
            return True
    hepsi = [h for h in hepsi if taze(h)]
    hepsi.sort(key=lambda h: h.get("zaman_utc", ""), reverse=True)
    return hepsi[:en_fazla]
