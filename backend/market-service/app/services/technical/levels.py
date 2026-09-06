"""Yapısal destek/direnç bölgeleri — günlük çerçeve.

Zincir: aday → küme (bölge) → temas olayı → güç → seçim. Birim ATR14'tür
(`A` = son ATR; tarihsel temas o günün ATR'siyle ölçülür), böylece aynı kural
sakin ve çalkantılı dönemde aynı anlamı taşır ve sonuç fiyat çerçevesinden
bağımsızdır (spot ↔ vadeli farkı yalnız yuvarlak sayı adaylarını etkiler).

* **Adaylar** dört kaynaktan: fraktal salınımlar (`swings.py`), çağıranın verdiği
  pivotlar (bu modül pivot hesaplamaz, `(etiket, değer)` çifti alır), 20/60/250
  günlük uç değerler ve yuvarlak sayılar. Kaynak ağırlıkları `LevelParams`
  içindedir. Sağ kanadı eksik salınım ve son `wing` mumdaki uç değer
  **DEVELOPING**: yarım ağırlık, asla hedef ya da "test ediliyor" değil.
* **Kümeleme** fiyat sırasında tek geçiş; aday, ağırlıklı merkeze `tol` kadar
  yakınsa VE kümenin ilk üyesine `span` kadar yakınsa katılır. İkinci koşul
  tam-bağlantı (complete-linkage) tavanıdır: yalnız komşuya bakan zincirleme,
  ölçüldüğünde birbirinden ATR'lerce uzak seviyeleri tek bölgede topluyordu.
* **Temas olayı**: mum aralığı bölgeye o günün ATR'sinin çeyreği kadar yaklaşır.
  Ardışık temaslar tek olaydır; yeni olay için arada bölgeden en az 1 ATR uzak
  bir kapanış gerekir — on günlük konsolidasyon bir testtir, on değil. Bölgenin
  **oluşum** olayı (kökeni tanımlayan en eski mumu içeren olay) test sayılmaz:
  bir tepenin kendi mumları o tepeyi test etmez. Sonraki üyelerin oluşumları
  (çift tepe) ise testtir — bu yüzden dışlanan yalnız en eski tanımlayıcı mumdur.
* **Güç** altı bileşenin ağırlıklı toplamı; her temas 90 günlük yarı ömürle eskir.
  Hiç test edilmemiş bölge `min_strength`'in altında kalır (en çok 28; yalnız
  son mumda DEVELOVING üye varsa tazelik 1 sayılır ve 38'e çıkabilir — o bölge
  zaten hedef olamaz). Son sınıflanmış olay kırılımsa güç tazeliğiyle kısılır.
* **Seçim**: fiyatın `margin` içinde durduğu bölge "test ediliyor"dur, hedef değil
  (`session.nearest_levels` ile aynı kural). En yakın destek eşik üstü bölgeler
  arasında üst kenarı en yüksek olandır; direnç simetrik. Bir yanda eşik üstü
  bölge yoksa durum o yan için `NO_VALID_*` olur ve en güçlü eşik altı bölge
  `weakest_ignored` içinde bildirilir; pivot yedeğini çağıran ekler.

Karmaşıklık: salınım O(n·kanat), kümeleme O(m log m), temas sayımı O(n·K),
K ≤ `max_zones`. İleri bakış yok: `bars[:t]` ile alınan sonuç yalnız o mumlara
bağlıdır. numpy yok; belirlenimci.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date

from .candles import Candle
from .indicators import IndicatorParams, atr
from .swings import STATUS_DEVELOPING, swing_points

SOURCE_SWING = "swing"
SOURCE_PIVOT = "pivot"
SOURCE_RANGE = "range_extreme"
SOURCE_ROUND = "round"
# Kümede sıralama ve ad seçimi için kaynak önceliği (yalnız eşitlik bozucu).
_SOURCE_RANK = {SOURCE_SWING: 0, SOURCE_PIVOT: 1, SOURCE_RANGE: 2, SOURCE_ROUND: 3}

KIND_SUPPORT = "SUPPORT"
KIND_RESISTANCE = "RESISTANCE"

SIDE_ABOVE = "ABOVE"
SIDE_BELOW = "BELOW"

CLASS_REJECTION = "REJECTION"
CLASS_BREAK = "BREAK"
CLASS_NEUTRAL = "NEUTRAL"
CLASS_PENDING = "PENDING"
_HELD = (CLASS_REJECTION, CLASS_NEUTRAL)

LABEL_STRONG = "STRONG"
LABEL_MODERATE = "MODERATE"
LABEL_WEAK = "WEAK"

STATUS_OK = "OK"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STATUS_FLAT_MARKET = "FLAT_MARKET"
SIDE_OK = "OK"
NO_VALID_SUPPORT = "NO_VALID_SUPPORT"
NO_VALID_RESISTANCE = "NO_VALID_RESISTANCE"

COMPONENT_NAMES = ("touch", "rejection", "hold", "confluence", "recency", "source")


@dataclass(frozen=True)
class LevelParams:
    """Motorun bütün sayıları. Ağırlık tabloları hash'lenebilir kalsın diye
    sözlük değil çift demeti; `source_weight` / `component_weight` ile okunur."""

    swing_wing: int = 3
    swing_lookback: int = 250
    range_extreme_windows: tuple[int, ...] = (20, 60, 250)
    round_step: float = 100.0          # ≤ 0 → yuvarlak sayı adayı üretilmez
    source_weights: tuple[tuple[str, float], ...] = (
        (SOURCE_SWING, 1.0), (SOURCE_PIVOT, 0.8), (SOURCE_RANGE, 0.7), (SOURCE_ROUND, 0.2))
    developing_factor: float = 0.5
    cluster_atr_factor: float = 0.5
    cluster_span_atr: float = 1.0
    zone_min_half_width_atr: float = 0.25
    scan_atr: float = 12.0
    max_zones: int = 40
    touch_atr_factor: float = 0.25
    touch_gap_days: int = 3            # mum (işlem günü) cinsinden boşluk
    event_separation_atr: float = 1.0
    reaction_window_bars: int = 3
    reaction_min_atr: float = 1.0
    break_min_atr: float = 0.5
    break_confirm_closes: int = 2
    rejection_cap_atr: float = 3.0
    recency_half_life_days: float = 90.0
    touch_scale: float = 2.0
    confluence_scale: float = 1.5
    weights: tuple[tuple[str, float], ...] = (
        ("touch", 0.30), ("rejection", 0.20), ("hold", 0.20),
        ("confluence", 0.15), ("recency", 0.10), ("source", 0.05))
    break_damping: float = 0.5
    min_strength: int = 30
    strong: int = 67
    moderate: int = 34
    min_bars: int = 35
    # `source = min(1, Σ temel ağırlık / source_scale)`: iki tam ağırlıklı kaynak
    # bileşeni doyurur.
    source_scale: float = 2.0

    def source_weight(self, source_type: str) -> float:
        return dict(self.source_weights).get(source_type, 0.0)

    def component_weight(self, name: str) -> float:
        return dict(self.weights).get(name, 0.0)


@dataclass(frozen=True)
class Candidate:
    price: float
    source_type: str        # swing | pivot | range_extreme | round
    label: str              # SWING_HIGH / R1 / HIGH_250 / ROUND
    weight: float           # temel ağırlık × (DEVELOPING ise developing_factor)
    date: date | None
    confirmed: bool
    index: int | None       # tanımlayıcı mumun indeksi; pivot ve yuvarlakta None


@dataclass(frozen=True)
class TouchEvent:
    start: int
    end: int
    date: date              # olayın son temas mumu
    side: str               # ABOVE | BELOW — fiyat hangi yandan geldi
    klass: str              # REJECTION | BREAK | NEUTRAL | PENDING
    rejection: float | None  # ATR cinsinden geri dönüş (kırpılı); PENDING'de None
    weight: float           # 0,5 ** (yaş_gün / yarı_ömür)


@dataclass(frozen=True)
class Zone:
    id: str
    mid: float
    low: float
    high: float
    kind: str               # SUPPORT | RESISTANCE (mid < referans → destek)
    strength: int
    label: str              # STRONG | MODERATE | WEAK
    name: str               # en ağır üyenin etiketi
    sources: tuple[Candidate, ...]
    source_types: tuple[str, ...]
    touches: int
    rejections: int
    breaks: int
    pending: int
    last_touch: date | None
    last_break: date | None
    confirmed: bool         # en az bir üye CONFIRMED; değilse hedef/test olamaz
    components: dict[str, float]
    distance_pct: float
    distance_usd: float
    distance_atr: float
    distance_sigma: float | None
    testing: bool


@dataclass(frozen=True)
class Levels:
    status: str             # OK | INSUFFICIENT_DATA | FLAT_MARKET
    as_of: date | None
    atr: float | None
    sigma: float | None
    cluster_tolerance: float | None
    margin_usd: float | None
    scan_range: tuple[float, float] | None
    min_strength: int
    zones: tuple[Zone, ...]
    nearest_support: str | None
    next_support: str | None
    nearest_resistance: str | None
    next_resistance: str | None
    testing: tuple[str, ...]
    weakest_ignored: dict | None   # {'support': {...}, 'resistance': {...}} — yalnız eksik yanlar
    side_status: dict[str, str]


# --- adaylar -------------------------------------------------------------------

def _in_range(value: float, low: float, high: float) -> bool:
    return low <= value <= high


def _range_extremes(bars: Sequence[Candle], params: LevelParams) -> list[tuple[str, int, float]]:
    """(etiket, indeks, fiyat) — pencere başına en yüksek/en düşük mum.

    Aynı mum birden çok pencerenin ucuysa bir kez sayılır, etiketi en uzun
    pencereden gelir (250 günlük zirve zaten 20 günlük zirvedir; üç kez
    saymak kaynak bileşenini boş yere doyururdu). Eşit uçlarda en yeni mum
    tanımlayıcıdır; eskisi o seviyeye geri dönüş, yani bir temastır.
    """
    count = len(bars)
    found: dict[tuple[str, int], str] = {}
    for window in sorted(w for w in params.range_extreme_windows if 0 < w <= count):
        indices = range(count - window, count)
        high_index = max(indices, key=lambda i: (bars[i].high, i))
        low_index = min(indices, key=lambda i: (bars[i].low, -i))
        found[("HIGH", high_index)] = f"HIGH_{window}"
        found[("LOW", low_index)] = f"LOW_{window}"
    out: list[tuple[str, int, float]] = []
    for (kind, index), label in found.items():
        price = bars[index].high if kind == "HIGH" else bars[index].low
        out.append((label, index, price))
    return out


def candidates(bars: Sequence[Candle], atr_series: Sequence[float | None], reference: float,
               pivot_levels: Sequence[tuple[str, float]], params: LevelParams = LevelParams()
               ) -> list[Candidate]:
    """Tarama aralığındaki (referans ± scan_atr·A) bütün seviye adayları.

    Sıra: salınımlar, pivotlar, uç değerler, yuvarlak sayılar. ATR yoksa boş.
    """
    if not bars or not atr_series:
        return []
    unit = atr_series[-1]
    if unit is None or unit <= 0.0:
        return []
    low_bound, high_bound = reference - params.scan_atr * unit, reference + params.scan_atr * unit
    last = len(bars) - 1
    out: list[Candidate] = []

    base = params.source_weight(SOURCE_SWING)
    for swing in swing_points(bars, params.swing_wing, lookback=params.swing_lookback):
        if not _in_range(swing.price, low_bound, high_bound):
            continue
        developing = swing.status == STATUS_DEVELOPING
        out.append(Candidate(swing.price, SOURCE_SWING, f"SWING_{swing.kind}",
                             base * (params.developing_factor if developing else 1.0),
                             swing.date, not developing, swing.index))

    base = params.source_weight(SOURCE_PIVOT)
    for label, value in pivot_levels:
        price = float(value)
        if _in_range(price, low_bound, high_bound):
            out.append(Candidate(price, SOURCE_PIVOT, str(label), base, None, True, None))

    base = params.source_weight(SOURCE_RANGE)
    for label, index, price in _range_extremes(bars, params):
        if not _in_range(price, low_bound, high_bound):
            continue
        # Son `wing` mumdaki uç değerin sağ kanadı eksik: salınımla aynı kural,
        # yoksa DEVELOPING tepe uç değer kılığında "onaylı" sayılırdı.
        developing = index + params.swing_wing > last
        out.append(Candidate(price, SOURCE_RANGE, label,
                             base * (params.developing_factor if developing else 1.0),
                             bars[index].date, not developing, index))

    step = params.round_step
    if step > 0.0:
        base = params.source_weight(SOURCE_ROUND)
        k = math.ceil(low_bound / step)
        while k * step <= high_bound:
            out.append(Candidate(k * step, SOURCE_ROUND, "ROUND", base, None, True, None))
            k += 1
    return out


# --- kümeleme ------------------------------------------------------------------

def _sort_key(candidate: Candidate) -> tuple:
    return (candidate.price, _SOURCE_RANK.get(candidate.source_type, 9), candidate.label,
            -1 if candidate.index is None else candidate.index)


def cluster_zones(cands: Sequence[Candidate], atr: float, params: LevelParams = LevelParams()
                  ) -> list[tuple[Candidate, ...]]:
    """Fiyat sırasında tek geçişle küme; her küme fiyat sırasında üyeler.

    Katılma koşulu: |fiyat − ağırlıklı merkez| ≤ tol VE fiyat − küme_min ≤ span.
    """
    tolerance = params.cluster_atr_factor * atr
    span = params.cluster_span_atr * atr
    ordered = sorted(cands, key=_sort_key)
    clusters: list[list[Candidate]] = []
    weight_sum = price_sum = 0.0
    cluster_min = 0.0
    for candidate in ordered:
        if clusters:
            centroid = price_sum / weight_sum if weight_sum > 0.0 else clusters[-1][-1].price
            if (abs(candidate.price - centroid) <= tolerance
                    and candidate.price - cluster_min <= span):
                clusters[-1].append(candidate)
                weight_sum += candidate.weight
                price_sum += candidate.weight * candidate.price
                continue
        clusters.append([candidate])
        weight_sum, price_sum, cluster_min = candidate.weight, candidate.weight * candidate.price, candidate.price
    return [tuple(group) for group in clusters]


def _zone_bounds(members: Sequence[Candidate], atr: float, params: LevelParams
                 ) -> tuple[float, float, float]:
    """(mid, low, high): ağırlıklı merkez; kenarlar üyeleri kapsar ve en az
    mid ∓ zone_min_half_width_atr·A kadar açılır."""
    total = sum(m.weight for m in members)
    if total > 0.0:
        mid = sum(m.weight * m.price for m in members) / total
    else:
        mid = sum(m.price for m in members) / len(members)
    half = params.zone_min_half_width_atr * atr
    low = min(min(m.price for m in members), mid - half)
    high = max(max(m.price for m in members), mid + half)
    return mid, low, high


def _primary(members: Sequence[Candidate]) -> Candidate:
    """Ad veren üye: en ağır, sonra onaylı, sonra en yeni mum."""
    return max(members, key=lambda m: (m.weight, m.confirmed, -1 if m.index is None else m.index))


def _source_types(members: Sequence[Candidate]) -> tuple[str, ...]:
    seen: list[str] = []
    for member in members:
        if member.source_type not in seen:
            seen.append(member.source_type)
    return tuple(seen)


# --- temas olayları ------------------------------------------------------------

def _classify(bars: Sequence[Candle], end: int, side: str, low: float, high: float,
              unit: float, params: LevelParams) -> tuple[str, float | None]:
    """Olay sonrası `reaction_window_bars` kapanışına göre sınıf ve geri dönüş
    şiddeti. Bütün eşikler olayın son mumundaki ATR (`unit`) ile ölçülür."""
    window = params.reaction_window_bars
    if window < 1:
        return CLASS_NEUTRAL, 0.0           # tepki penceresi yoksa sınıflama da yok
    if end + window > len(bars) - 1:
        return CLASS_PENDING, None
    closes = [bars[end + k].close for k in range(1, window + 1)]
    if side == SIDE_ABOVE:
        depths = [low - c for c in closes]      # > 0: uzak kenar (alt) aşıldı
        aways = [c - high for c in closes]      # yaklaşılan yandan uzaklaşma
    else:
        depths = [c - high for c in closes]
        aways = [low - c for c in closes]
    first_cross = next((k for k, d in enumerate(depths) if d >= params.break_min_atr * unit), None)
    if first_cross is not None:
        beyond = sum(1 for d in depths[first_cross:] if d > 0.0)
        if beyond >= params.break_confirm_closes:
            return CLASS_BREAK, 0.0
    move = max(aways)
    if all(d <= 0.0 for d in depths) and move >= params.reaction_min_atr * unit:
        return CLASS_REJECTION, min(move / unit, params.rejection_cap_atr)
    return CLASS_NEUTRAL, 0.0


def touch_events(bars: Sequence[Candle], atr_series: Sequence[float | None], low: float, high: float,
                 *, exclude: frozenset[int] = frozenset(), params: LevelParams = LevelParams()
                 ) -> list[TouchEvent]:
    """Bölgeye [low, high] temas olayları, zaman sırasında.

    Mum t temas eder ⇔ L_t ≤ high + f·ATR_t ve H_t ≥ low − f·ATR_t. ATR'si
    olmayan (ısınma) mumlar değerlendirilmez. `exclude` içindeki bir mumu
    kapsayan olay bütünüyle atılır: seviyenin oluşum mumları onu test etmez,
    komşuları da (tepe mumu dışlanıp komşuları sayılsaydı her yeni tepe bir
    bedava temas kazanırdı).
    """
    count = len(bars)
    if count == 0:
        return []
    as_of = bars[-1].date
    mid = (low + high) / 2.0
    factor, separation, gap = params.touch_atr_factor, params.event_separation_atr, params.touch_gap_days
    spans: list[list[int]] = []
    last_far = -1
    for t in range(count):
        unit = atr_series[t] if t < len(atr_series) else None
        if unit is None or unit <= 0.0:
            continue
        bar = bars[t]
        if bar.low <= high + factor * unit and bar.high >= low - factor * unit:
            # Boşluk kısa ya da arada uzak kapanış yoksa aynı olay sürer.
            if spans and (t - spans[-1][1] <= gap or not (spans[-1][1] < last_far < t)):
                spans[-1][1] = t
            else:
                spans.append([t, t])
        # Aynı mumun uzak kapanışı kendi temasını bölmez; sonrakileri böler.
        if bar.close > high + separation * unit or bar.close < low - separation * unit:
            last_far = t

    out: list[TouchEvent] = []
    for start, end in spans:
        if any(start <= index <= end for index in exclude):
            continue
        unit = atr_series[end]
        assert unit is not None
        previous_close = bars[start - 1].close if start > 0 else bars[start].close
        side = SIDE_ABOVE if previous_close >= mid else SIDE_BELOW
        klass, rejection = _classify(bars, end, side, low, high, unit, params)
        age_days = (as_of - bars[end].date).days
        weight = 0.5 ** (age_days / params.recency_half_life_days)
        out.append(TouchEvent(start, end, bars[end].date, side, klass, rejection, weight))
    return out


# --- güç -----------------------------------------------------------------------

def score_zone(events: Sequence[TouchEvent], members: Sequence[Candidate], *, last_index: int,
               params: LevelParams = LevelParams()) -> tuple[int, dict[str, float]]:
    """(güç 0–100, bileşenler). Bileşenler 0–1 arasında; `base` ağırlıklı
    toplam, `break_factor` son olay kırılımsa 1 − damping·w."""
    touch_sum = sum(e.weight for e in events)
    touch = 1.0 - math.exp(-touch_sum / params.touch_scale)

    classified = [e for e in events if e.klass != CLASS_PENDING]
    classified_weight = sum(e.weight for e in classified)
    if classified_weight > 0.0:
        rejection = sum(e.weight * min((e.rejection or 0.0) / params.rejection_cap_atr, 1.0)
                        for e in classified) / classified_weight
    else:
        rejection = 0.0
    held = sum(e.weight for e in classified if e.klass in _HELD)
    hold = (held + 1.0) / (classified_weight + 2.0)   # ağırlıklı Laplace: test yoksa 0,5

    types = _source_types(members)
    confluence = 1.0 - math.exp(-(len(types) - 1) / params.confluence_scale)

    if any(m.index == last_index and not m.confirmed for m in members):
        recency = 1.0
    elif events:
        recency = max(events, key=lambda e: e.end).weight
    else:
        recency = 0.0
    source = min(1.0, sum(params.source_weight(m.source_type) for m in members) / params.source_scale)

    components = {"touch": touch, "rejection": rejection, "hold": hold,
                  "confluence": confluence, "recency": recency, "source": source}
    base = sum(params.component_weight(name) * components[name] for name in COMPONENT_NAMES)
    last_classified = max(classified, key=lambda e: e.end) if classified else None
    break_factor = 1.0
    if last_classified is not None and last_classified.klass == CLASS_BREAK:
        break_factor = 1.0 - params.break_damping * last_classified.weight
    components["base"] = base
    components["break_factor"] = break_factor
    return int(round(100.0 * base * break_factor)), components


def strength_label(strength: int, params: LevelParams = LevelParams()) -> str:
    if strength >= params.strong:
        return LABEL_STRONG
    if strength >= params.moderate:
        return LABEL_MODERATE
    return LABEL_WEAK


# --- seçim ---------------------------------------------------------------------

def _empty(status: str, as_of: date | None, unit: float | None, sigma: float | None,
           params: LevelParams) -> Levels:
    return Levels(status=status, as_of=as_of, atr=unit, sigma=sigma, cluster_tolerance=None,
                  margin_usd=None, scan_range=None, min_strength=params.min_strength, zones=(),
                  nearest_support=None, next_support=None, nearest_resistance=None,
                  next_resistance=None, testing=(), weakest_ignored=None,
                  side_status={"support": NO_VALID_SUPPORT, "resistance": NO_VALID_RESISTANCE})


def _summary(zone: Zone) -> dict:
    return {"id": zone.id, "mid": zone.mid, "low": zone.low, "high": zone.high, "kind": zone.kind,
            "strength": zone.strength, "label": zone.label, "name": zone.name,
            "touches": zone.touches, "distance_pct": zone.distance_pct}


def _build_zone(members: tuple[Candidate, ...], bars: Sequence[Candle],
                atr_series: Sequence[float | None], unit: float, reference: float,
                sigma: float | None, margin: float, params: LevelParams) -> Zone:
    mid, low, high = _zone_bounds(members, unit, params)
    indices = [m.index for m in members if m.index is not None]
    # Yalnız köken (en eski tanımlayıcı mum) dışlanır; sonraki üyelerin oluşumu
    # seviyenin testidir (çift tepe iki kez dokunmuştur, sıfır değil).
    exclude = frozenset({min(indices)}) if indices else frozenset()
    events = touch_events(bars, atr_series, low, high, exclude=exclude, params=params)
    strength, components = score_zone(events, members, last_index=len(bars) - 1, params=params)
    breaks = [e for e in events if e.klass == CLASS_BREAK]
    confirmed = any(m.confirmed for m in members)
    testing = confirmed and (low - margin <= reference <= high + margin)
    delta = mid - reference
    return Zone(
        id="", mid=mid, low=low, high=high,
        kind=KIND_SUPPORT if mid < reference else KIND_RESISTANCE,
        strength=strength, label=strength_label(strength, params), name=_primary(members).label,
        sources=members, source_types=_source_types(members),
        touches=len(events),
        rejections=sum(1 for e in events if e.klass == CLASS_REJECTION),
        breaks=len(breaks), pending=sum(1 for e in events if e.klass == CLASS_PENDING),
        last_touch=max((e.date for e in events), default=None),
        last_break=max((e.date for e in breaks), default=None),
        confirmed=confirmed, components=components,
        distance_pct=mid / reference - 1.0, distance_usd=delta, distance_atr=delta / unit,
        distance_sigma=(delta / (reference * sigma)) if sigma is not None and sigma > 0.0 else None,
        testing=testing)


def _assign_ids(zones: Sequence[Zone]) -> list[Zone]:
    seen: dict[str, int] = {}
    out: list[Zone] = []
    for zone in zones:
        base = f"z-{round(zone.mid)}"
        seen[base] = seen.get(base, 0) + 1
        out.append(replace(zone, id=base if seen[base] == 1 else f"{base}-{seen[base]}"))
    return out


def analyze_levels(bars: Sequence[Candle], reference: float, *,
                   pivot_levels: Sequence[tuple[str, float]] = (), sigma: float | None = None,
                   params: LevelParams = LevelParams(),
                   indicator_params: IndicatorParams = IndicatorParams()) -> Levels:
    """Tamamlanmış günlük mumlardan referans fiyata göre bölge haritası.

    `reference` canlı fiyat olabilir; mesafeler ona göredir, ATR mumlardan.
    `pivot_levels` çağıranın (haftalık klasik, Fibonacci…) hazır seviyeleri.
    """
    if not (isinstance(reference, (int, float)) and math.isfinite(reference) and reference > 0.0):
        raise ValueError(f"reference pozitif sonlu sayı olmalı, {reference!r} verildi")
    as_of = bars[-1].date if bars else None
    if len(bars) < params.min_bars:
        return _empty(STATUS_INSUFFICIENT_DATA, as_of, None, sigma, params)
    atr_series = atr(bars, indicator_params.atr_period)
    unit = atr_series[-1]
    if unit is None or unit <= 0.0:
        return _empty(STATUS_FLAT_MARKET, as_of, unit, sigma, params)

    margin = params.touch_atr_factor * unit
    cands = candidates(bars, atr_series, reference, pivot_levels, params)
    zones = [_build_zone(members, bars, atr_series, unit, reference, sigma, margin, params)
             for members in cluster_zones(cands, unit, params)]
    zones.sort(key=lambda z: (-z.strength, abs(z.mid - reference), z.mid))
    zones = _assign_ids(zones[:params.max_zones])

    eligible = [z for z in zones if z.confirmed]
    testing = sorted((z for z in eligible if z.testing), key=lambda z: (abs(z.mid - reference), z.mid))
    supports = [z for z in eligible if z.high < reference - margin]
    resistances = [z for z in eligible if z.low > reference + margin]
    valid_supports = sorted((z for z in supports if z.strength >= params.min_strength),
                            key=lambda z: (-z.high, -z.strength, z.mid))
    valid_resistances = sorted((z for z in resistances if z.strength >= params.min_strength),
                               key=lambda z: (z.low, -z.strength, z.mid))

    side_status: dict[str, str] = {}
    weakest: dict[str, dict] = {}
    for side, valid, pool, failure in (("support", valid_supports, supports, NO_VALID_SUPPORT),
                                       ("resistance", valid_resistances, resistances, NO_VALID_RESISTANCE)):
        side_status[side] = SIDE_OK if valid else failure
        if not valid:
            ignored = [z for z in pool if z.strength < params.min_strength]
            if ignored:
                weakest[side] = _summary(max(ignored, key=lambda z: (z.strength, -abs(z.mid - reference))))

    def pick(items: Sequence[Zone], position: int) -> str | None:
        return items[position].id if len(items) > position else None

    return Levels(
        status=STATUS_OK, as_of=as_of, atr=unit, sigma=sigma,
        cluster_tolerance=params.cluster_atr_factor * unit, margin_usd=margin,
        scan_range=(reference - params.scan_atr * unit, reference + params.scan_atr * unit),
        min_strength=params.min_strength, zones=tuple(zones),
        nearest_support=pick(valid_supports, 0), next_support=pick(valid_supports, 1),
        nearest_resistance=pick(valid_resistances, 0), next_resistance=pick(valid_resistances, 1),
        testing=tuple(z.id for z in testing), weakest_ignored=weakest or None,
        side_status=side_status)
