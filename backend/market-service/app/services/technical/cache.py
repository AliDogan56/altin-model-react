"""Teknik analiz sonucunun tek girişli, tek uçuşlu bellek önbelleği.

Neden anahtar tabanlı, süre tabanlı değil: analiz saf ve belirlenimcidir —
aynı girdi (günlük seri, gün içi seri, UTC gün, yapılandırma) aynı sonucu
verir. Doğruluk bu yüzden **anahtardan** gelir: girdi değişmediyse yeniden
hesaplamak boşa iştir, değiştiyse eski sonucu bir saniye bile sunmak yanlıştır.
TTL yalnız güvenlik ağıdır: anahtar üretiminde bir alan unutulursa ya da bir
girdi anahtara yansımadan değişirse sonuç sonsuza kadar bayat kalmasın diye
`cfg.cache_ttl_seconds` sonra aynı anahtarla bile yeniden hesaplanır.

Neden tek giriş: anahtar zamanla ilerler (bugünün tarihi, son 5 dakikalık mum,
günlük serinin son günü); eski bir anahtar bir daha sorulmaz. Birden fazla
giriş tutmak yalnız bellek yığardı. Farklı anahtar gelince eski giriş atılır;
bellek üst sınırı tam olarak bir analizdir.

Neden anahtar başına kilit (tek uçuş): pano açılışında aynı anda birkaç istek
gelir; soğuk önbellekte hepsi ayrı ayrı onlarca milisaniyelik hesabı
çalıştırırdı. Kilitle ilk istek hesaplar, kalanlar bekleyip aynı sonucu alır.
Kilit anahtar başına tutulur ki geçiş anında (eski anahtar hesaplanırken yeni
anahtarlı bir istek gelirse) yeni istek eskisini beklemek zorunda kalmasın.
Kilit sözlüğü de sınırlıdır: bekleyeni kalmayan anahtarın kilidi silinir.

Saat dışarıdan verilir (`clock`), böylece TTL testte gerçek zaman beklemeden
sınanır; modül `asyncio` dışında hiçbir şeye bağlı değildir.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Awaitable, Callable, Generic, Mapping, TypeVar

T = TypeVar("T")
Clock = Callable[[], datetime]

# RFC 7232 etagc: 0x21 ve 0x23-0x7E (tırnak ve boşluk dışındaki görünür ASCII).
# Anahtar ETag başlığına olduğu gibi yazıldığı için kaynak adı gibi serbest
# metin alanları bu kümeye indirgenir; anlamı değişmez, yalnız başlık geçerli kalır.
_NOT_ETAG_CHAR = re.compile(r"[^\x21\x23-\x7e]")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def analysis_key(daily: Mapping[str, Any], intraday: Mapping[str, Any] | None, *,
                 today: date, config_hash: str) -> str:
    """Analizin girdilerini özetleyen anahtar.

    Alanlar sırasıyla: günlük serinin son günü ve satır sayısı, kaynağı ve
    yedeğe düşülüp düşülmediği (aynı gün Yahoo'dan gelen seri xaus'tan gelenle
    aynı sonucu vermez), gün içi son mumun damgası ve mum sayısı (gün içi yoksa
    `None|0`), UTC bugün (oluşan gün ve dönem tamamlanma kuralı buna bağlı) ve
    yapılandırma özeti. Bu alanlardan biri değişmeden analiz değişemez; yükün
    tamamını özetlemek (1257 satırı hash'lemek) hiçbir ek doğruluk getirmezdi.
    """
    points = daily.get("points") or []
    bars = (intraday or {}).get("bars") or []
    parts = (
        str(points[-1].get("d")) if points else None,
        len(points),
        daily.get("source"),
        bool(daily.get("fallback", False)),
        str(bars[-1].get("t")) if bars else None,
        len(bars),
        today.isoformat(),
        config_hash,
    )
    return "|".join(_NOT_ETAG_CHAR.sub("_", "" if p is None else ("1" if p is True else "0" if p is False else str(p)))
                    for p in parts)


@dataclass(frozen=True)
class Entry(Generic[T]):
    key: str
    value: T
    computed_at: datetime


class AnalysisCache(Generic[T]):
    """Tek giriş, anahtar başına tek uçuş, güvenlik TTL'li önbellek.

    `get_or_compute(key, compute)` → `(değer, meta)`; `meta` = `hit` (önbellekten
    mi geldi), `computed_at` (değerin hesaplandığı an, ISO-8601 UTC) ve
    `cache_key`. `ttl_seconds <= 0` önbelleği fiilen kapatır (her istek yeniden
    hesaplar); bu, "anahtar yanlış olabilir" şüphesinde güvenli çıkış yoludur.
    """

    def __init__(self, ttl_seconds: int, *, clock: Clock = utc_now) -> None:
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._entry: Entry[T] | None = None
        self._locks: dict[str, asyncio.Lock] = {}
        self._waiting: dict[str, int] = {}

    @property
    def entry(self) -> Entry[T] | None:
        return self._entry

    def pending_keys(self) -> tuple[str, ...]:
        """Şu an kilidi tutulan/beklenen anahtarlar; testte kilit sızıntısını ölçmek için."""
        return tuple(self._locks)

    async def get_or_compute(self, key: str, compute: Callable[[], Awaitable[T]]) -> tuple[T, dict[str, Any]]:
        # Bekleyen sayacı kilitten önce artar: aynı anda gelen N istek aynı Lock
        # nesnesini paylaşmalı; sayaç sıfıra inince kilit sözlükten düşer ki
        # geçmiş her anahtar için bir Lock birikmesin.
        self._waiting[key] = self._waiting.get(key, 0) + 1
        lock = self._locks.setdefault(key, asyncio.Lock())
        try:
            async with lock:
                fresh = self._fresh(key)
                if fresh is not None:
                    return fresh.value, self._meta(fresh, hit=True)
                value = await compute()
                entry = Entry(key, value, self._clock())
                # Tek giriş: farklı anahtarlı eski değer burada atılır. Hesap
                # hata verirse `_entry` dokunulmaz kalır; kilit `async with` ile
                # her durumda bırakılır, sonraki istek yeniden dener.
                self._entry = entry
                return value, self._meta(entry, hit=False)
        finally:
            self._waiting[key] -= 1
            if self._waiting[key] == 0:
                del self._waiting[key]
                self._locks.pop(key, None)

    def _fresh(self, key: str) -> Entry[T] | None:
        entry = self._entry
        if entry is None or entry.key != key:
            return None
        age = (self._clock() - entry.computed_at).total_seconds()
        return entry if age < self.ttl_seconds else None

    @staticmethod
    def _meta(entry: Entry[T], *, hit: bool) -> dict[str, Any]:
        stamp = entry.computed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return {"hit": hit, "computed_at": stamp, "cache_key": entry.key}
