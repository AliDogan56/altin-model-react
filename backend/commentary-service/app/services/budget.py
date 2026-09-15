"""Kota bütçesi (saf): metin ve ses üretimini günlük sayı ve aralıkla sınırlar.

Sağlayıcı sınırları ölçüldü (2026-09-15): Groq gpt-oss-120b 1.000 istek/gün, 8.000 token/dk
(yanıt başlıklarından); Gemini ücretsiz katman sayıları yalnız AI Studio panosunda görünür,
önizleme modellerinde (konuşma dahil) daha dar ve duyurusuz değişebilir. Bu yüzden servis
sağlayıcıya güvenmez: kendi bütçesini sayar, 429 gelince soğuma süresine girer ve durumu
`/v1/commentary/job` içinde `budget` olarak gösterir. Günlük sayaç Gemini'nin sıfırlama
saatine göre (varsayılan Pasifik gece yarısı) hesaplanır; Groq için de yeterince tutucu.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo


def day_start(now: dt.datetime, tz_name: str) -> dt.datetime:
    """Kota gününün başlangıcı (UTC): verilen dilimde bugünün 00:00'ı."""
    local = now.astimezone(ZoneInfo(tz_name))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(dt.UTC)


def parse_version(version: str) -> dt.datetime | None:
    """`20260915T070122Z` → UTC datetime; bozuksa None."""
    try:
        return dt.datetime.strptime(version, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.UTC)
    except (TypeError, ValueError):
        return None


def count_since(stamps: list[dt.datetime | None], since: dt.datetime) -> int:
    return sum(1 for s in stamps if s is not None and s >= since)


def text_allowed(runs_today: int, max_per_day: int, *, force: bool = False) -> tuple[bool, str]:
    if force:
        return True, "force"
    if max_per_day and runs_today >= max_per_day:
        return False, f"günlük metin sınırı doldu ({runs_today}/{max_per_day})"
    return True, ""


def narration_allowed(*, now: dt.datetime, attempts_today: int, max_per_day: int, last_ok: dt.datetime | None,
                      min_interval_minutes: int, last_attempt: dt.datetime | None, retry_minutes: int,
                      cooldown_until: dt.datetime | None) -> tuple[bool, str]:
    """Ses üretimi şimdi denensin mi. Sayaç denemeleri sayar (başarısız da kota harcar)."""
    if cooldown_until and now < cooldown_until:
        return False, f"kota soğuması ({(cooldown_until - now).total_seconds() / 60:.0f} dk kaldı)"
    if max_per_day and attempts_today >= max_per_day:
        return False, f"günlük ses sınırı doldu ({attempts_today}/{max_per_day})"
    if last_ok is not None:
        since = (now - last_ok).total_seconds() / 60
        if since < min_interval_minutes:
            return False, f"son sesten {since:.0f} dk geçti (< {min_interval_minutes})"
    if last_attempt is not None and (now - last_attempt).total_seconds() / 60 < retry_minutes:
        return False, f"yeniden deneme aralığı dolmadı ({retry_minutes} dk)"
    return True, ""
