"""Fraktal salınım noktaları — günlük çerçeve.

Bir mum, sol kanadındaki N mumun hepsinden **katı** yüksek ve sağ kanadındaki N
mumun hepsinden yüksek-ya-da-eşitse tepe (`HIGH`); dip simetrik. Katı/eşit
asimetrisi eşit tepeleri tek noktaya indirger: plato oluşunca ilk mum kazanır,
sonrakiler sol kanatta ona eşit kaldıkları için elenir.

Sağ kanat henüz tamamlanmamışsa (`i + N > son`) ama mum eldeki sağ mumların
hepsini karşılıyorsa nokta **DEVELOPING** döner. Bu nokta gelecekte silinebilir
(daha yüksek bir mum gelince); seviye motoru ona yarım ağırlık verir ve hiçbir
zaman hedef ya da "test ediliyor" seviyesi yapmaz.

Gün içi çerçevedeki öncül (`session.py`, kanat 2, 40 mum) hem sol hem sağ kanatta
eşitliğe izin veriyordu; günlük çerçevede kanat 3 ve 250 mum, ayrıca tamamlanmamış
tepe ayrı işaretlenir.

İleri bakış yok: her karar yalnız `bars` içindeki mumlara bakar; `bars[:t]` ile
alınan CONFIRMED noktalar t'den sonra gelen mumlardan etkilenmez. Karmaşıklık
O(n·N). numpy yok.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

KIND_HIGH = "HIGH"
KIND_LOW = "LOW"
STATUS_CONFIRMED = "CONFIRMED"
STATUS_DEVELOPING = "DEVELOPING"


class _Bar(Protocol):
    """Ördek tipli mum: `date`, `high`, `low` yeter."""

    date: date
    high: float
    low: float


@dataclass(frozen=True)
class Swing:
    kind: str      # HIGH | LOW
    index: int     # `bars` içindeki mutlak indeks (pencereye göre değil)
    date: date
    price: float   # tepede high, dipte low
    status: str    # CONFIRMED | DEVELOPING


def _is_swing(values: Sequence[float], index: int, wing: int, *, high: bool) -> str | None:
    """`index` bir salınım mı? Durum döner; değilse None.

    Sol kanat katı (`>` / `<`), sağ kanat eşitliğe açık (`>=` / `<=`). Sağ kanat
    kısa kaldıysa eldeki mumlar yeter, ama sonuç DEVELOPING olur."""
    value = values[index]
    for j in range(index - wing, index):
        if (values[j] >= value) if high else (values[j] <= value):
            return None
    last = len(values) - 1
    for j in range(index + 1, min(index + wing, last) + 1):
        if (values[j] > value) if high else (values[j] < value):
            return None
    return STATUS_CONFIRMED if index + wing <= last else STATUS_DEVELOPING


def swing_points(bars: Sequence[_Bar], wing: int = 3, *, lookback: int | None = None) -> list[Swing]:
    """Son `lookback` mum içindeki fraktal tepe ve dipler, indeks sırasında.

    Sol kanat pencerenin dışına taşabilir: pencere yalnız hangi mumların aday
    olduğunu sınırlar, karşılaştırma bütün seriyi görür. Böylece pencerenin ilk
    mumları da salınım olabilir ve pencere kaydıkça nokta kaybolup geri gelmez.
    Aynı mum hem tepe hem dip olabilir (dev aralıklı tek mum); ikisi de döner,
    tepe önce.
    """
    if not isinstance(wing, int) or isinstance(wing, bool) or wing < 1:
        raise ValueError(f"wing pozitif tam sayı olmalı, {wing!r} verildi")
    if lookback is not None and (not isinstance(lookback, int) or lookback < 1):
        raise ValueError(f"lookback pozitif tam sayı ya da None olmalı, {lookback!r} verildi")
    count = len(bars)
    if count <= wing:
        return []
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    start = wing if lookback is None else max(wing, count - lookback)
    out: list[Swing] = []
    for index in range(start, count):
        status = _is_swing(highs, index, wing, high=True)
        if status is not None:
            out.append(Swing(KIND_HIGH, index, bars[index].date, highs[index], status))
        status = _is_swing(lows, index, wing, high=False)
        if status is not None:
            out.append(Swing(KIND_LOW, index, bars[index].date, lows[index], status))
    return out
