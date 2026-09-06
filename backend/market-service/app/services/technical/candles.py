"""Mum normalizasyonu, dönem toplama ve "son tamamlanmış dönem" kuralı.

Teknik analiz paketinin bütün hesapları buradan çıkan mumları okur; dış
kaynağın kaprisleri (metin olarak gelen sayılar, `null` alanlar, sırasız ya da
yinelenen satırlar) yalnız bu modülde karşılanır. Ölçülen gerçekler:

* Günlük seri (`/v1/market/xau`) yalnız tarih, kapanış, yüksek ve düşük taşır —
  **açılış ve hacim yok**. 1257 satırın 55'inde `h == l`; bunlar hatalı değil,
  kaynağın gün içi aralığı vermediği günler. Atılmaz.
* Kapanış aralığın dışına çıkarsa satır atılmaz, aralık kapanışı kapsayacak
  şekilde **genişletilir** ve sayılır. Bugün böyle satır yok (ölçüldü: 0) ama
  kaynak dış; pivot formülleri `close` ∈ [low, high] varsayar.
* Yinelenen tarihte **son** kayıt kalır: kaynak düzeltme yayımladığında yeni
  değer listenin sonunda gelir.
* Gün içi 5 dakikalık akışta `o` boş gelebilir; önceki mumun kapanışı açılışın
  en iyi tahminidir (5 dakikalık boşlukta fiyat sıçraması istisna). `v` boşsa
  **None kalır**, 0'a çevrilmez — hacim var mı yok mu kararı çağırana ait.

Dönem tamamlanması bilinçli olarak katıdır ve iki ölçülmüş hatadan çıkar:

1. Oluşmakta olan dönem asla kullanılmaz; ama "sondan bir önceki" de koşulsuz
   alınmaz. 22 Ağustos cumartesi pivot kartı bir hafta bayat seviyeler
   gösteriyordu; hafta cumartesiden itibaren tamamlanmış sayılır
   (`momentum_service.last_complete_week` ve `domain/pivots.ts` ile aynı kural).
2. Takvim haftayı bitmiş saysa bile **kapanış mumu yoksa** dönem verilmez.
   2026-08-31'de kaynak bir saatten uzun 503 döndü ve 300 sn önbellek kırpık
   bir haftadan pivot üretilmesine izin verdi. Tatil (cuma mumu yok) için
   hoşgörü süresi var; dolmadan `MISSING_CLOSING_BAR` döner.

Bütün fonksiyonlar saf ve belirlenimcidir; yalnız verilen mumları görür,
ileriye bakmaz. Karmaşıklık O(n log n) (sıralama), gerisi tek geçiş.
"""

from __future__ import annotations

import calendar
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum


class Timeframe(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    SEMIANNUAL = "SEMIANNUAL"


# Takvim dönemlerinin ay uzunluğu; günlük ve haftalık ay ile ölçülmez.
_MONTHS_PER_PERIOD = {Timeframe.MONTHLY: 1, Timeframe.QUARTERLY: 3, Timeframe.SEMIANNUAL: 6}

# Kalite ve tamamlanma durumları. Metin olarak taşınır (JSON'a doğrudan girer).
STATUS_OK = "OK"
STATUS_NO_DATA = "NO_DATA"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STATUS_INCOMPLETE_PERIOD = "INCOMPLETE_PERIOD"
STATUS_MISSING_CLOSING_BAR = "MISSING_CLOSING_BAR"

# Tek mumdan getiri bile hesaplanamaz; en az iki gün / iki mum gerekir.
DAILY_MINIMUM = 2
INTRADAY_MINIMUM = 2

# ISO takvimi: pazartesi 1, cuma 5, pazar 7. Haftalık kapanış mumu cumaya
# aittir (altın cuma 21:00 UTC'de kapanır); pazartesiden cumaya 4 gün.
_ISO_FRIDAY = 5
_FRIDAY_OFFSET = 4
_WEEK_DAYS = 7


@dataclass(frozen=True)
class Candle:
    """Günlükte işlem günü; toplanmış dönemde `date` dönem BAŞLANGICI
    (pazartesi / ayın 1'i / çeyrek başı), `end_date` dönemdeki son mumun tarihi."""

    date: date
    high: float
    low: float
    close: float
    open: float | None = None
    volume: float | None = None
    end_date: date | None = None
    bars: int = 1


@dataclass(frozen=True)
class IntradayBar:
    time: datetime  # her zaman UTC'ye çevrilmiş, tz bilgili
    open: float
    high: float
    low: float
    close: float
    volume: float | None


@dataclass(frozen=True)
class Quality:
    received: int
    kept: int
    dropped_invalid: int
    dropped_duplicate: int
    range_widened: int
    status: str  # OK | INSUFFICIENT_DATA | NO_DATA
    first_date: date | None
    last_date: date | None


@dataclass(frozen=True)
class CompletionParams:
    """Dönem tamamlanma kuralı.

    `week_complete_weekday`: haftanın pazartesi başlangıcından itibaren kaç
    gün geçince hafta bitmiş sayılır (0 = pazartesi, 5 = cumartesi). Cumartesi,
    repoda ölçülüp seçilen kural: cuma kapanışı gelmiştir, hafta bayat kalmaz.
    `grace_days`: beklenen kapanış mumu (tatil vb.) gelmediyse dönem sonundan
    bu kadar gün geçince dönem yine kabul edilir; yoksa tatil haftası hiç
    pivot üretmezdi.
    """

    week_complete_weekday: int = 5
    grace_days: int = 2


# --- ayrıştırma yardımcıları ---------------------------------------------------

def _require_sequence(value: object, name: str) -> None:
    # str de bir Sequence'tir ama satır listesi değildir; bilerek dışlanır.
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{name} bir dizi olmalı, {type(value).__name__} geldi")


def _to_float(value: object) -> float | None:
    """Sayı ya da sayısal metin → sonlu float; aksi None. bool sayı sayılmaz."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _to_price(value: object) -> float | None:
    number = _to_float(value)
    return number if number is not None and number > 0 else None


def _to_volume(value: object) -> float | None:
    # Negatif hacim anlamsız; 0 ise gerçekten sıfır (Yahoo kapanış mumunda öyle).
    number = _to_float(value)
    return number if number is not None and number >= 0 else None


def _to_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _to_utc(value: object) -> datetime | None:
    """ISO damga → UTC. Saat dilimi yoksa UTC varsayılır; varsa UTC'ye çevrilir."""
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, str):
        try:
            stamp = datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    else:
        return None
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _widen(low: float, high: float, *anchors: float) -> tuple[float, float, bool]:
    """Aralığı verilen fiyatları kapsayacak şekilde genişletir; ters gelmiş
    high/low da burada düzelir. Üçüncü değer aralığın değişip değişmediği."""
    lo = min(low, high, *anchors)
    hi = max(low, high, *anchors)
    return lo, hi, (lo, hi) != (low, high)


def _quality(received: int, kept: Sequence[date], invalid: int, duplicate: int,
             widened: int, minimum: int) -> Quality:
    if not kept:
        status = STATUS_NO_DATA
    elif len(kept) < minimum:
        status = STATUS_INSUFFICIENT_DATA
    else:
        status = STATUS_OK
    return Quality(received=received, kept=len(kept), dropped_invalid=invalid,
                   dropped_duplicate=duplicate, range_widened=widened, status=status,
                   first_date=kept[0] if kept else None, last_date=kept[-1] if kept else None)


# --- normalizasyon ---------------------------------------------------------------

def _daily_candle(row: object) -> tuple[Candle | None, bool]:
    if not isinstance(row, Mapping):
        return None, False
    day = _to_date(row.get("d"))
    close, high, low = _to_price(row.get("c")), _to_price(row.get("h")), _to_price(row.get("l"))
    if day is None or close is None or high is None or low is None:
        return None, False
    low, high, widened = _widen(low, high, close)
    return Candle(date=day, high=high, low=low, close=close), widened


def normalize_daily(points: Sequence[Mapping], *, minimum: int = DAILY_MINIMUM
                    ) -> tuple[list[Candle], Quality]:
    """Ham günlük satırları temiz, kronolojik, tarihçe tekil mum listesine çevirir.

    Bozuk satır hiçbir zaman hata fırlatmaz; atılır ve `Quality` içinde sayılır.
    Yalnız `points` dizi değilse TypeError. Yinelenen tarihte son *geçerli*
    kayıt kalır.
    """
    _require_sequence(points, "points")
    by_date: dict[date, Candle] = {}
    invalid = duplicate = widened = 0
    for row in points:
        candle, was_widened = _daily_candle(row)
        if candle is None:
            invalid += 1
            continue
        widened += int(was_widened)
        if candle.date in by_date:
            duplicate += 1
        by_date[candle.date] = candle
    candles = [by_date[key] for key in sorted(by_date)]
    quality = _quality(len(points), [c.date for c in candles], invalid, duplicate, widened, minimum)
    return candles, quality


@dataclass(frozen=True)
class _RawBar:
    """Açılışı henüz doldurulmamış gün içi mum; sıralama ve tekilleştirme
    bitmeden önceki mum bilinemediği için ara adım gerekir."""

    time: datetime
    open: float | None
    high: float
    low: float
    close: float
    volume: float | None


def _intraday_bar(row: object) -> tuple[_RawBar | None, bool]:
    if not isinstance(row, Mapping):
        return None, False
    stamp = _to_utc(row.get("t"))
    close, high, low = _to_price(row.get("c")), _to_price(row.get("h")), _to_price(row.get("l"))
    if stamp is None or close is None or high is None or low is None:
        return None, False
    open_ = _to_price(row.get("o"))
    # Yalnız kaynağın verdiği açılış aralığı genişletir; doldurulan açılış
    # (önceki kapanış) o mumun gerçek aralığına ait değildir.
    anchors = (close,) if open_ is None else (close, open_)
    low, high, widened = _widen(low, high, *anchors)
    return _RawBar(stamp, open_, high, low, close, _to_volume(row.get("v"))), widened


def normalize_intraday(bars: Sequence[Mapping]) -> tuple[list[IntradayBar], Quality]:
    """Ham 5 dakikalık mumları UTC damgalı, sıralı, tekil listeye çevirir.

    `o` boşsa önceki mumun kapanışı, ilk mumda kendi kapanışı yazılır.
    `v` boş ya da negatifse None kalır; 0'a çevrilmez.
    """
    _require_sequence(bars, "bars")
    by_time: dict[datetime, _RawBar] = {}
    invalid = duplicate = widened = 0
    for row in bars:
        raw, was_widened = _intraday_bar(row)
        if raw is None:
            invalid += 1
            continue
        widened += int(was_widened)
        if raw.time in by_time:
            duplicate += 1
        by_time[raw.time] = raw
    out: list[IntradayBar] = []
    previous_close: float | None = None
    for key in sorted(by_time):
        raw = by_time[key]
        open_ = raw.open if raw.open is not None else (
            previous_close if previous_close is not None else raw.close)
        out.append(IntradayBar(raw.time, open_, raw.high, raw.low, raw.close, raw.volume))
        previous_close = raw.close
    quality = _quality(len(bars), [b.time.date() for b in out], invalid, duplicate, widened,
                       INTRADAY_MINIMUM)
    return out, quality


# --- takvim ---------------------------------------------------------------------

def period_key(day: date, timeframe: Timeframe) -> date:
    """Günün ait olduğu dönemin başlangıç tarihi.

    Hafta ISO takvimiyle pazartesi–pazar: kaynakta pazar tarihli mum yok
    (ölçüldü: yalnız 1–5 numaralı ISO günler), o yüzden pazar gecesi açılışını
    ayrıca ele almaya gerek yok.
    """
    if timeframe is Timeframe.DAILY:
        return day
    if timeframe is Timeframe.WEEKLY:
        return day - timedelta(days=day.isoweekday() - 1)
    span = _MONTHS_PER_PERIOD[timeframe]
    month = ((day.month - 1) // span) * span + 1
    return date(day.year, month, 1)


def period_end(start: date, timeframe: Timeframe) -> date:
    """Dönemin takvim sonu (hafta için pazar, ay için ayın son günü…).
    `start` dönem başı değilse önce döneme oturtulur."""
    start = period_key(start, timeframe)
    if timeframe is Timeframe.DAILY:
        return start
    if timeframe is Timeframe.WEEKLY:
        return start + timedelta(days=_WEEK_DAYS - 1)
    last_month = start.month + _MONTHS_PER_PERIOD[timeframe] - 1
    return date(start.year, last_month, calendar.monthrange(start.year, last_month)[1])


def _expected_closing_day(start: date, timeframe: Timeframe) -> date:
    """Dönemin son beklenen işlem günü: haftada cuma, diğerlerinde dönemin
    son hafta içi günü. Tatiller bilinmez; onları hoşgörü süresi karşılar."""
    if timeframe is Timeframe.DAILY:
        return start
    if timeframe is Timeframe.WEEKLY:
        return start + timedelta(days=_FRIDAY_OFFSET)
    end = period_end(start, timeframe)
    while end.isoweekday() > _ISO_FRIDAY:
        end -= timedelta(days=1)
    return end


# --- toplama --------------------------------------------------------------------

@dataclass
class _Bucket:
    """Tek geçişte dönem toplayan biriktirici."""

    start: date
    open: float | None = None
    high: float = -math.inf
    low: float = math.inf
    close: float = 0.0
    volume: float = 0.0
    volume_complete: bool = True
    bars: int = 0
    end_date: date | None = None

    def add(self, candle: Candle) -> None:
        if self.open is None and candle.open is not None:
            self.open = candle.open
        self.high = max(self.high, candle.high)
        self.low = min(self.low, candle.low)
        self.close = candle.close
        # Bir mum bile hacimsizse toplam yanıltır; None döner.
        if candle.volume is None:
            self.volume_complete = False
        else:
            self.volume += candle.volume
        self.bars += candle.bars
        self.end_date = candle.end_date or candle.date

    def build(self) -> Candle:
        return Candle(date=self.start, high=self.high, low=self.low, close=self.close,
                      open=self.open, volume=self.volume if self.volume_complete else None,
                      end_date=self.end_date, bars=self.bars)


def aggregate(candles: Sequence[Candle], timeframe: Timeframe) -> list[Candle]:
    """Günlük mumları dönem mumlarına toplar; DAILY listeyi kopyalar.

    Girdi sıralı varsayılmaz (ucuz bir sıralama, yanlış "son kapanış"tan
    ucuz). AÇILIŞ dönemdeki ilk boş olmayan açılış, HACİM her mumda varsa toplam.
    """
    if timeframe is Timeframe.DAILY:
        # Sıralı kopya: pivot modülü sırasız girdiyle 'dün' diye 2023 mumunu seçmişti.
        return sorted(candles, key=lambda c: c.date)
    out: list[Candle] = []
    bucket: _Bucket | None = None
    for candle in sorted(candles, key=lambda c: c.date):
        start = period_key(candle.date, timeframe)
        if bucket is None or bucket.start != start:
            if bucket is not None:
                out.append(bucket.build())
            bucket = _Bucket(start)
        bucket.add(candle)
    if bucket is not None:
        out.append(bucket.build())
    return out


# --- tamamlanma -----------------------------------------------------------------

def _calendar_complete(start: date, timeframe: Timeframe, today: date,
                       params: CompletionParams) -> bool:
    if timeframe is Timeframe.DAILY:
        return today > start
    if timeframe is Timeframe.WEEKLY:
        return today >= start + timedelta(days=params.week_complete_weekday)
    return today > period_end(start, timeframe)


def _grace_elapsed(start: date, timeframe: Timeframe, today: date, params: CompletionParams) -> bool:
    return today >= period_end(start, timeframe) + timedelta(days=params.grace_days)


def _latest_complete_start(timeframe: Timeframe, today: date, params: CompletionParams) -> date:
    """Takvime göre bitmiş sayılan ve içinde işlem günü bulunan en son dönemin
    başlangıcı — veriden bağımsız. Hafta ve ay her zaman hafta içi gün taşır;
    günlükte hafta sonu beklenen mum yoktur, cumaya geri gidilir."""
    current = period_key(today, timeframe)
    if not _calendar_complete(current, timeframe, today, params):
        current = period_key(current - timedelta(days=1), timeframe)
    if timeframe is Timeframe.DAILY:
        while current.isoweekday() > _ISO_FRIDAY:
            current -= timedelta(days=1)
    return current


def previous_completed_period(candles: Sequence[Candle], timeframe: Timeframe, today: date,
                              params: CompletionParams = CompletionParams()
                              ) -> tuple[Candle | None, str]:
    """Son TAMAMLANMIŞ dönemin toplanmış mumu ve durum.

    Oluşmakta olan dönem hiçbir koşulda dönmez. Takvimce bitmiş dönemde
    kapanış mumu yoksa (kırpık hafta, tatil) hoşgörü süresi dolana kadar
    `MISSING_CLOSING_BAR` ve mum None — kırpık haftadan pivot üretilmez.
    Takvimce bitmiş bir dönem veride *hiç* yoksa da aynı kural işler: akış
    bir hafta boyunca kesik kaldıysa eski hafta "güncel" diye sunulmaz.
    """
    periods = aggregate(candles, timeframe)
    if not periods:
        return None, STATUS_INSUFFICIENT_DATA
    index = len(periods) - 1
    while index >= 0 and not _calendar_complete(periods[index].date, timeframe, today, params):
        index -= 1
    if index < 0:
        return None, STATUS_INCOMPLETE_PERIOD
    period = periods[index]
    latest = _latest_complete_start(timeframe, today, params)
    if period.date < latest and not _grace_elapsed(latest, timeframe, today, params):
        return None, STATUS_MISSING_CLOSING_BAR
    last_bar = period.end_date or period.date
    if last_bar == _expected_closing_day(period.date, timeframe) or _grace_elapsed(
            period.date, timeframe, today, params):
        return period, STATUS_OK
    return None, STATUS_MISSING_CLOSING_BAR
