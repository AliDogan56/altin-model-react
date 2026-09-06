"""Referans fiyat: bütün seviye uzaklıkları bu tek sayıya göre hesaplanır.

Neden tek çerçeve: günlük seri (xaus, kaynağın kendi beyanıyla GC=F türevi) ile
gün içi 5 dk barlar (Yahoo GC=F) aynı enstrümandır; canlı Harem spot ise ~%1
farklı ve hafta sonu bayattır. Ölçüldü (2026-09-06): aynı merdiven Harem'de
P/S1, kapanışta R1/P veriyordu — çerçeve karıştırmak en yakın seviyeyi
değiştiriyor. Harem burada **hiç okunmaz** (`LIVE_QUOTE_NOT_USED`); arayüz onu
yalnız başlıkta canlı kotasyon olarak gösterir.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Sequence

from .candles import Candle, IntradayBar

FRAME_INTRADAY = "intraday_close"
FRAME_DAILY = "daily_close"
STATUS_OK = "OK"
STATUS_INTRADAY_STALE = "INTRADAY_STALE"
STATUS_INTRADAY_UNAVAILABLE = "INTRADAY_UNAVAILABLE"
STATUS_NO_DATA = "NO_DATA"
NOTE = "LIVE_QUOTE_NOT_USED"


@dataclass(frozen=True)
class ReferencePrice:
    value: float | None
    frame: str | None
    instrument: str
    as_of: datetime | None
    daily_date: date | None
    daily_close: float | None
    status: str
    note: str = NOTE


def choose_reference(daily: Sequence[Candle], intraday: Sequence[IntradayBar] | None,
                     *, instrument: str = "GC=F") -> ReferencePrice:
    """Gün içi son bar günlük serinin son gününden eski değilse onun kapanışı,
    yoksa günlük kapanış. `daily` tamamlanmış (oluşan gün atılmış) mumlardır.

    Tarih karşılaştırması UTC gün bazında: gün içi barın tarihi günlük son
    mumun tarihinden küçükse gün içi akış bayattır (ör. akış saatlerce
    durmuşsa) ve günlük kapanış daha güncel bilgidir.
    """
    if not daily:
        return ReferencePrice(None, None, instrument, None, None, None, STATUS_NO_DATA)
    last = daily[-1]
    if intraday:
        bar = intraday[-1]
        bar_day = bar.time.astimezone(timezone.utc).date()
        if bar_day >= last.date:
            return ReferencePrice(float(bar.close), FRAME_INTRADAY, instrument, bar.time,
                                  last.date, float(last.close), STATUS_OK)
        return ReferencePrice(float(last.close), FRAME_DAILY, instrument,
                              datetime.combine(last.date, datetime.min.time(), timezone.utc),
                              last.date, float(last.close), STATUS_INTRADAY_STALE)
    return ReferencePrice(float(last.close), FRAME_DAILY, instrument,
                          datetime.combine(last.date, datetime.min.time(), timezone.utc),
                          last.date, float(last.close), STATUS_INTRADAY_UNAVAILABLE)
