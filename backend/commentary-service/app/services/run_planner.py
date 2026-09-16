"""Tam tur mu, hızlı tur mu (saf): girdiler değişmediyse beş rolü yeniden koşturmak israftır.

Ölçüldü (2026-09-15, canlı 6 tur): ardışık sürümlerin metin benzerliği %9–17, yani aynı piyasa
durumu her saat sıfırdan yazılıyor; tur başına 22 bin giriş token. Fiyat dışındaki girdiler
(takvim, faiz beklentisi, enflasyon, pozisyon, makro seriler, başlıklar) değişmediyse yalnız
anlatıcı yeniden yazar (hızlı tur, ~5 bin token); değiştiyse ya da son tam tur eskidiyse tam tur.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

HEADLINE_WINDOW = 6
NEW_HEADLINES_FOR_FULL = 3


def input_fingerprint(package: dict, headlines: list[dict], commentators: list[dict] | None = None) -> dict:
    """Fiyat ve zaman dışındaki girdilerin özeti; karşılaştırılabilir, JSON'a yazılabilir.
    `commentators`: yorumcu gözcüsünün masaya verdiği kayıtlar; yön ya da ana iddia değişince tam tur gerekir."""
    faiz = {k: v for k, v in (package.get("faiz_beklentisi") or {}).items() if k not in ("tarih", "kaynak", "nasil_anilir")}
    return {
        "takvim": (package.get("takvim") or {}).get("olaylar"),
        "faiz": faiz,
        "enflasyon": package.get("enflasyon"),
        "pozisyon": package.get("pozisyon"),
        "makro_son": package.get("makro_son"),
        "basliklar": sorted((h.get("baslik") or "")[:120] for h in headlines[:HEADLINE_WINDOW]),
        "yorumcular": sorted(f"{c.get('etiket') or c.get('ad')}|{c.get('yon')}|{(c.get('ana_iddia') or '')[:80]}" for c in (commentators or [])),
    }


def fingerprint_hash(fp: dict) -> str:
    return hashlib.sha256(json.dumps(fp, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:12]


def inputs_changed(prev: dict | None, cur: dict) -> tuple[bool, str]:
    if not prev:
        return True, "önceki tam turun parmak izi yok"
    for key in ("takvim", "faiz", "enflasyon", "pozisyon", "makro_son", "yorumcular"):
        if json.dumps(prev.get(key), sort_keys=True, default=str) != json.dumps(cur.get(key), sort_keys=True, default=str):
            return True, f"{key} değişti"
    new = set(cur.get("basliklar") or []) - set(prev.get("basliklar") or [])
    if len(new) >= NEW_HEADLINES_FOR_FULL:
        return True, f"{len(new)} yeni başlık"
    return False, "girdiler aynı"


def plan_run(*, configured_mode: str, force: bool, brief_exists: bool, prev: dict | None, cur: dict,
             last_full_at: dt.datetime | None, now: dt.datetime, full_max_age_minutes: int) -> tuple[str, str]:
    """Döndürür: ("full" | "fast", sebep)."""
    if configured_mode == "fast":
        return "fast", "yapılandırma fast"
    if force:
        return "full", "force"
    if not brief_exists:
        return "full", "brif yok"
    changed, why = inputs_changed(prev, cur)
    if changed:
        return "full", why
    if last_full_at is not None and full_max_age_minutes and (now - last_full_at).total_seconds() / 60 >= full_max_age_minutes:
        return "full", f"son tam tur {int((now - last_full_at).total_seconds() / 60)} dk önce (≥ {full_max_age_minutes})"
    return "fast", why
