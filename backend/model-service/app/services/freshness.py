"""Donmuş girdilerin tespiti.

Sorun (2026-08-31'de ölçüldü): `core_cpi_yoy` 2026-08-03'ten beri hiç
değişmemişti — aylık yayımlanan bir seri olduğu için 20 işlem günü boyunca
aynı sayı. Buna rağmen 30 günlük tahminin +%3,54'ünün +3,02 puanını tek başına
o taşıyordu. Değeri 2,15, eğitim penceresinin **mutlak minimumu**; model hiç
görmediği bir bölgede ekstrapolasyon yapıyordu.

Kural: bir girdi son `FROZEN_AFTER_ROWS` işlem gününde hiç değişmediyse,
tahmin edilen dönem hakkında **güncel bilgi taşımıyor** demektir; tahmin
anında eğitim ortalamasına çekilir (ölçekli uzayda sıfırlanır).

Eşik ölçümle seçildi: 2026-08-31 itibarıyla diğer makro girdilerin en uzun
sabit kalma süresi 4 gün, `core_cpi_yoy` ise 20 gün. 15 ikisini rahatça ayırır
ve normal yayın gecikmelerini yanlışlıkla yakalamaz.

**Bu, girdiyi eğitimden çıkarmak değildir.** Çıkarıp yeniden eğitmek denendi ve
ölçülen beceriyi yarıya indirdi (30g +%26,3 -> +%11,8) üstelik yönü de
değiştirmedi; ağ aynı rejimi diğer makro girdiler üzerinden yeniden öğrendi.
Burada model olduğu gibi kalır, yalnız bilgi taşımayan girdiye dayanmaz.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

FROZEN_AFTER_ROWS = 15


def frozen_features(
    rows: Sequence[dict], names: Iterable[str], min_rows: int = FROZEN_AFTER_ROWS,
) -> tuple[str, ...]:
    """Son `min_rows` satır boyunca hiç değişmemiş girdilerin adları.

    `rows` tarih sıralı olmalı (en yeni sonda). Yeterli satır yoksa hiçbir girdi
    donmuş sayılmaz: az veriyle "değişmiyor" demek yanıltıcı olurdu.
    """
    if min_rows < 1 or len(rows) <= min_rows:
        return ()
    window = rows[-(min_rows + 1):]
    donmus = []
    for name in names:
        values = [row.get(name) for row in window]
        if any(value in (None, "") for value in values):
            continue                       # eksik veri ayrı bir durum, burada karar verilmez
        if len(set(values)) == 1:
            donmus.append(name)
    return tuple(donmus)
