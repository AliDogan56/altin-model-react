"""Pivot seviyeleri (klasik / Fibonacci / Camarilla) ve fiyat merdiveni.

`frontend/src/domain/pivots.ts`'in sunucudaki karşılığı. Cebir ve takvim kuralı
ölçülüp birebir taşındı; eşitlik `tests/fixtures/baseline_live_20260906.json`
ve `baseline_history_20260906.json` ile (iki fiyat çerçevesi × 4 varyant canlı,
6 tarihsel gün × 4 varyant) sabitlenmiştir. Formüller, r = H − L olmak üzere:

* Klasik:    P = (H+L+C)/3; R1 = 2P−L, R2 = P+r, R3 = H+2(P−L);
             S1 = 2P−H, S2 = P−r, S3 = L−2(H−P)
* Fibonacci: R_k = P + f_k·r, S_k = P − f_k·r, f = (0,382; 0,618; 1)
* Camarilla: R_k = C + r·1,1·m_k, S_k = C − r·1,1·m_k, m = (1/12, 1/6, 1/4, 1/2);
             P yalnız gösterim için eklenir. Camarilla kapanışa çapalıdır:
             kapanış aralığın ucundaysa S1–S3 P'nin ÜSTÜNE çıkar. Bu yüzden
             seviyeler ada göre değil **değere göre** azalan sıralanır.

Dönem seçimi `candles.previous_completed_period`'a bırakılır; takvim kuralı
(hafta cumartesiden, ay bittiğinde tamamlanmış) tek yerde yaşar. Oradan
`MISSING_CLOSING_BAR` dönerse — takvimce bitmiş dönemin kapanış mumu henüz
gelmemiş — bir önceki döneme DÜŞÜLÜR ve durum `PERIOD_INCOMPLETE_FALLBACK`
olarak, beklenen mumun tarihiyle (`missing_bar_for`) bildirilir. Ölçülen hata
bu: 2026-08-31'de kaynak bir saatten uzun 503 döndü, 300 sn önbellek kırpık
haftayı tam hafta gibi sundu ve seviyeler eksik haftadan hesaplandı. Kırpık
dönemden seviye üretmek yerine bir önceki tam dönem gösterilir.

Merdiven: seviyeler azalan sıralanır, fiyat aralarına yerleşir. `margin_usd`
"üzerinde durulan seviye hedef değildir" kuralıdır (kullanıcı bildirdi:
gösterilen seviye çoktan kırılmıştı): fiyata marj kadar yakın seviyeler
`TESTING` sayılır ve en yakın hedef aranırken atlanır. Marj 0 iken kural
arayüzdeki `buildLadder` ile aynıdır (`above = value >= price`, en yakın üst =
üsttekilerin sonuncusu, en yakın alt = alttakilerin ilki). Tek fark fiyatın bir
seviyeye **tam** eşit olduğu ölçü-sıfır durum: arayüz o seviyeyi hedef sayar,
burada test edilen seviye olarak bildirilir — fiyat seviyenin üzerindeyken
"kırılacak seviye bu" demek, kuralın çıkış nedeninin ta kendisiydi.

Bütün fonksiyonlar saf ve belirlenimcidir; `today`'den sonraki mum hiçbir
hesaba girmez (ileriye bakmaz). `compute_all` girdiyi `today`'e kadar keser,
yani aynı seri üzerinde geçmiş bir güne bakmak o günün gördüğü veriyi görür.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum

# `_latest_complete_start` ve `_expected_closing_day` paket içi yardımcılardır.
# Takvim kuralının ikinci bir kopyası (frontend'de ve momentum_service'te
# yaşandı) ölçülmüş hataların kaynağıydı; kuralı burada yeniden yazmaktansa
# kardeş modülün tek uygulamasına bağlanmak bilinçli tercih.
from .candles import (
    STATUS_INCOMPLETE_PERIOD as CANDLE_INCOMPLETE_PERIOD,
    STATUS_MISSING_CLOSING_BAR as CANDLE_MISSING_CLOSING_BAR,
    STATUS_OK as CANDLE_OK,
    Candle,
    CompletionParams,
    Timeframe,
    _expected_closing_day,
    _latest_complete_start,
    aggregate,
    period_end,
    previous_completed_period,
)


class PivotMethod(str, Enum):
    CLASSIC = "CLASSIC"
    FIBONACCI = "FIBONACCI"
    CAMARILLA = "CAMARILLA"


class PivotPeriod(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


_TIMEFRAME = {PivotPeriod.DAILY: Timeframe.DAILY, PivotPeriod.WEEKLY: Timeframe.WEEKLY,
              PivotPeriod.MONTHLY: Timeframe.MONTHLY}

# Dönem durumu. Metin olarak taşınır (JSON'a doğrudan girer).
STATUS_OK = "OK"
STATUS_PERIOD_INCOMPLETE_FALLBACK = "PERIOD_INCOMPLETE_FALLBACK"
STATUS_PERIOD_UNAVAILABLE = "PERIOD_UNAVAILABLE"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

# Seçilen dönemin neden "bitmiş" sayıldığı — kapanış mumu geldi mi, yoksa
# piyasa devam edip hoşgörü mü doldu; tüketici bayatlığı buradan okur.
COMPLETION_LAST_BAR_PRESENT = "LAST_BAR_PRESENT"
COMPLETION_SUCCEEDED_BY_LATER_BAR = "SUCCEEDED_BY_LATER_BAR"
COMPLETION_GRACE_ELAPSED = "GRACE_ELAPSED"
COMPLETION_NONE = "NONE"

ROLE_NEAREST_UP = "NEAREST_UP"
ROLE_NEAREST_DOWN = "NEAREST_DOWN"
ROLE_TESTING = "TESTING"
OUTSIDE_ABOVE_ALL = "ABOVE_ALL"
OUTSIDE_BELOW_ALL = "BELOW_ALL"
POSITION_ABOVE = "ABOVE"
POSITION_BELOW = "BELOW"
POSITION_AT = "AT"

PIVOT_NAME = "P"

Level = tuple[str, float]


@dataclass(frozen=True)
class PivotParams:
    """`fib_ratios` / `camarilla_multipliers` sırası R1, R2, … adlarını verir.
    `min_candles` arayüzün 40 kuralı: daha kısa seride pivot yerine
    `INSUFFICIENT_DATA`. `ladder_band_pct` her seviyenin çizim bandı (±%0,25;
    grafikteki `sr-zone` ile aynı düşünce, seviye bir çizgi değil bölgedir)."""

    fib_ratios: tuple[float, ...] = (0.382, 0.618, 1.0)
    camarilla_k: float = 1.1
    camarilla_multipliers: tuple[float, ...] = (1 / 12, 1 / 6, 1 / 4, 1 / 2)
    min_candles: int = 40
    ladder_band_pct: float = 0.0025


@dataclass(frozen=True)
class PivotSet:
    """Bir dönem × yöntem için seviyeler ve seçimin gerekçesi.

    `period_id`: günlükte mumun tarihi, haftalıkta ISO pazartesi, aylıkta
    `YYYY-MM`. `start` dönemin takvim başı, `end` dönemdeki son mumun tarihi.
    `status` seçim durumu, `completion` dönemin neden bitmiş sayıldığı,
    `missing_bar_for` (yalnız düşüş/ulaşılamama durumunda) beklenen ama
    gelmemiş kapanış mumunun tarihi. Seviye yoksa `levels` boş."""

    period: PivotPeriod
    method: PivotMethod
    period_id: str
    start: date | None
    end: date | None
    bars: int
    high: float | None
    low: float | None
    close: float | None
    completion: str
    status: str
    levels: tuple[Level, ...]
    missing_bar_for: date | None


@dataclass(frozen=True)
class LadderItem:
    """`distance` = value/price − 1 (arayüz kuralı), `distance_usd` = value − price,
    `distance_atr` ATR verilmişse dolar uzaklığının ATR katı. `above` arayüzün
    `value >= price` kuralı; `role` NEAREST_UP / NEAREST_DOWN / TESTING ya da
    None; `band` seviyenin ±`ladder_band_pct` bölgesi."""

    name: str
    value: float
    distance: float
    distance_usd: float
    distance_atr: float | None
    above: bool
    role: str | None
    band: tuple[float, float]


@dataclass(frozen=True)
class Ladder:
    """`items` değere göre azalan; `insert_at` fiyat satırının bu listede
    gireceği indeks (üstündeki seviye sayısı). `testing` marj içindeki seviye
    adları; `outside` fiyat tüm seviyelerin dışındaysa hangi uçtan;
    `position_vs_pivot` fiyatın P'ye göre yeri (marj içinde AT)."""

    price: float
    margin_usd: float
    items: tuple[LadderItem, ...]
    insert_at: int
    nearest_up: str | None
    nearest_down: str | None
    testing: tuple[str, ...]
    outside: str | None
    position_vs_pivot: str | None


# --- seviyeler -----------------------------------------------------------------

def _check_bar(high: float, low: float, close: float) -> None:
    for name, value in (("high", high), ("low", low), ("close", close)):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError(f"{name} sonlu bir sayı olmalı: {value!r}")
    if high < low:
        raise ValueError(f"high ({high}) low'dan ({low}) küçük olamaz")


def pivot_levels(high: float, low: float, close: float, method: PivotMethod,
                 params: PivotParams = PivotParams()) -> tuple[Level, ...]:
    """Tek bir dönem mumundan adlı seviyeler, değere göre AZALAN sırada.

    İşlem sırası arayüzdeki `levelsOf` ile aynıdır ki sonuç bit-bit eşleşsin
    (`(h + l + c) / 3`, `p + f·r`). Eşit değerler (aralık sıfır olan mumlar;
    fixture'da 55 gün böyle) giriş sırasını korur: R3, R2, R1, P, S1, S2, S3.
    """
    _check_bar(high, low, close)
    method = PivotMethod(method)
    pivot = (high + low + close) / 3
    span = high - low
    if method is PivotMethod.CLASSIC:
        named: list[Level] = [
            ("R3", high + 2 * (pivot - low)), ("R2", pivot + span), ("R1", 2 * pivot - low),
            (PIVOT_NAME, pivot),
            ("S1", 2 * pivot - high), ("S2", pivot - span), ("S3", low - 2 * (high - pivot)),
        ]
    elif method is PivotMethod.FIBONACCI:
        ups = [(f"R{k}", pivot + ratio * span) for k, ratio in enumerate(params.fib_ratios, 1)]
        downs = [(f"S{k}", pivot - ratio * span) for k, ratio in enumerate(params.fib_ratios, 1)]
        named = ups[::-1] + [(PIVOT_NAME, pivot)] + downs
    else:
        offsets = [span * params.camarilla_k * m for m in params.camarilla_multipliers]
        ups = [(f"R{k}", close + offset) for k, offset in enumerate(offsets, 1)]
        downs = [(f"S{k}", close - offset) for k, offset in enumerate(offsets, 1)]
        named = ups[::-1] + [(PIVOT_NAME, pivot)] + downs
    # Kararlı sıralama: eşit değerde giriş sırası korunur (Python ve V8 aynı).
    return tuple(sorted(named, key=lambda item: item[1], reverse=True))


# --- dönem seçimi ----------------------------------------------------------------

@dataclass(frozen=True)
class _Selection:
    bar: Candle | None
    status: str
    completion: str
    missing_bar_for: date | None


def _completion_of(bar: Candle, timeframe: Timeframe, candles: Sequence[Candle]) -> str:
    last_bar = bar.end_date or bar.date
    if last_bar == _expected_closing_day(bar.date, timeframe):
        return COMPLETION_LAST_BAR_PRESENT
    end = period_end(bar.date, timeframe)
    if any(candle.date > end for candle in candles):
        return COMPLETION_SUCCEEDED_BY_LATER_BAR
    return COMPLETION_GRACE_ELAPSED


def _select_period(candles: Sequence[Candle], period: PivotPeriod, today: date,
                   params: PivotParams, completion: CompletionParams) -> _Selection:
    if len(candles) < params.min_candles:
        return _Selection(None, STATUS_INSUFFICIENT_DATA, COMPLETION_NONE, None)
    timeframe = _TIMEFRAME[period]
    bar, status = previous_completed_period(candles, timeframe, today, completion)
    if status == CANDLE_OK and bar is not None:
        return _Selection(bar, STATUS_OK, _completion_of(bar, timeframe, candles), None)
    if status == CANDLE_MISSING_CLOSING_BAR:
        # Takvimce bitmiş en yeni dönemin kapanış mumu yok ve hoşgörü dolmadı.
        # Bir önceki dönem, o dönemden eski olduğu için hem takvimce bitmiş hem
        # hoşgörüsü dolmuştur; `previous_completed_period` aynı `today` ile onu
        # da reddederdi (eksik dönem varken eski dönemi "güncel" sunmaz), bu
        # yüzden düşüş burada açıkça yapılır ve durumla etiketlenir.
        latest = _latest_complete_start(timeframe, today, completion)
        missing = _expected_closing_day(latest, timeframe)
        older = aggregate([candle for candle in candles if candle.date < latest], timeframe)
        if not older:
            return _Selection(None, STATUS_PERIOD_UNAVAILABLE, COMPLETION_NONE, missing)
        previous = older[-1]
        return _Selection(previous, STATUS_PERIOD_INCOMPLETE_FALLBACK,
                          _completion_of(previous, timeframe, candles), missing)
    if status == CANDLE_INCOMPLETE_PERIOD:
        return _Selection(None, STATUS_PERIOD_UNAVAILABLE, COMPLETION_NONE, None)
    return _Selection(None, STATUS_INSUFFICIENT_DATA, COMPLETION_NONE, None)


def _period_id(start: date, period: PivotPeriod) -> str:
    return f"{start:%Y-%m}" if period is PivotPeriod.MONTHLY else start.isoformat()


def _pivot_set(selection: _Selection, period: PivotPeriod, method: PivotMethod,
               params: PivotParams) -> PivotSet:
    bar = selection.bar
    if bar is None:
        return PivotSet(period=period, method=method, period_id="", start=None, end=None, bars=0,
                        high=None, low=None, close=None, completion=selection.completion,
                        status=selection.status, levels=(), missing_bar_for=selection.missing_bar_for)
    return PivotSet(period=period, method=method, period_id=_period_id(bar.date, period),
                    start=bar.date, end=bar.end_date or bar.date, bars=bar.bars,
                    high=bar.high, low=bar.low, close=bar.close, completion=selection.completion,
                    status=selection.status,
                    levels=pivot_levels(bar.high, bar.low, bar.close, method, params),
                    missing_bar_for=selection.missing_bar_for)


def compute_all(candles: Sequence[Candle], today: date, params: PivotParams = PivotParams(),
                completion: CompletionParams = CompletionParams()
                ) -> dict[PivotPeriod, dict[PivotMethod, PivotSet]]:
    """Her dönem × yöntem için `PivotSet`. Dönem seçimi yönteme bağlı değildir;
    aynı mum üç yöntemle de hesaplanır. `today`'den sonraki mumlar görülmez.

    Girdi burada sıralanır: `aggregate` günlük çerçevede listeyi olduğu gibi
    kopyalar, sırasız girdide "son gün" yanlış çıkar (ölçüldü: karıştırılmış
    fixture 2023'ten bir günü bugünün mumu sandı)."""
    visible = sorted((candle for candle in candles if candle.date <= today), key=lambda c: c.date)
    out: dict[PivotPeriod, dict[PivotMethod, PivotSet]] = {}
    for period in PivotPeriod:
        selection = _select_period(visible, period, today, params, completion)
        out[period] = {method: _pivot_set(selection, period, method, params) for method in PivotMethod}
    return out


# --- merdiven --------------------------------------------------------------------

def build_ladder(levels: Sequence[Level], price: float, *, margin_usd: float = 0.0,
                 atr: float | None = None, params: PivotParams = PivotParams()) -> Ladder:
    """Seviyeleri fiyata göre yerleştirir ve en yakın hedefleri seçer.

    `nearest_up` fiyat + marjın üstündeki en düşük seviye, `nearest_down`
    fiyat − marjın altındaki en yüksek seviye; marj içindekiler `TESTING`.
    `insert_at` arayüz kuralıyla `value >= price` olan satır sayısıdır.
    Fiyat pozitif ve sonlu, marj negatif olmayan, ATR (verildiyse) pozitif
    olmalı; aksi ValueError — sıfır fiyatta merdivenin anlamı yoktur.
    """
    if not isinstance(price, (int, float)) or isinstance(price, bool) or not math.isfinite(price) or price <= 0:
        raise ValueError(f"price pozitif ve sonlu olmalı: {price!r}")
    if not math.isfinite(margin_usd) or margin_usd < 0:
        raise ValueError(f"margin_usd negatif olamaz: {margin_usd!r}")
    if atr is not None and (not math.isfinite(atr) or atr < 0):
        raise ValueError(f"atr negatif olamaz: {atr!r}")

    ordered: list[Level] = []
    for name, value in levels:
        if not math.isfinite(value):
            raise ValueError(f"{name} seviyesi sonlu değil: {value!r}")
        ordered.append((str(name), float(value)))
    ordered.sort(key=lambda item: item[1], reverse=True)

    above = [value >= price for _, value in ordered]
    testing = [abs(value - price) <= margin_usd for _, value in ordered]
    # Azalan listede üsttekiler öndedir: en yakın üst = uygun olanların sonuncusu,
    # en yakın alt = uygun olanların ilki. Test edilen seviye iki tarafa da girmez.
    up_index = next((i for i in range(len(ordered) - 1, -1, -1) if above[i] and not testing[i]), None)
    down_index = next((i for i in range(len(ordered)) if not above[i] and not testing[i]), None)

    items: list[LadderItem] = []
    for index, (name, value) in enumerate(ordered):
        role = (ROLE_TESTING if testing[index] else ROLE_NEAREST_UP if index == up_index
                else ROLE_NEAREST_DOWN if index == down_index else None)
        distance_usd = value - price
        items.append(LadderItem(
            name=name, value=value, distance=value / price - 1, distance_usd=distance_usd,
            distance_atr=distance_usd / atr if atr else None, above=above[index], role=role,
            band=(value * (1 - params.ladder_band_pct), value * (1 + params.ladder_band_pct))))

    outside = None
    if ordered:
        if all(value < price for _, value in ordered):
            outside = OUTSIDE_ABOVE_ALL
        elif all(value > price for _, value in ordered):
            outside = OUTSIDE_BELOW_ALL

    position = None
    pivot = next((value for name, value in ordered if name == PIVOT_NAME), None)
    if pivot is not None:
        position = (POSITION_AT if abs(pivot - price) <= margin_usd
                    else POSITION_ABOVE if price > pivot else POSITION_BELOW)

    return Ladder(price=price, margin_usd=margin_usd, items=tuple(items), insert_at=sum(above),
                  nearest_up=ordered[up_index][0] if up_index is not None else None,
                  nearest_down=ordered[down_index][0] if down_index is not None else None,
                  testing=tuple(name for (name, _), flag in zip(ordered, testing) if flag),
                  outside=outside, position_vs_pivot=position)
