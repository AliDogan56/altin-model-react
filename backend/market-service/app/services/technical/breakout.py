"""İki yönlü kırılım gücü: en yakın direnç (yukarı) ve en yakın destek (aşağı).

Soru "fiyat çıkar mı iner mi" değil: **mevcut itiş, o yandaki ilk seviyeyi
kırmaya yeter mi?** Bu soru iki yan için ayrı ayrı sorulur ve **her zaman iki
yan birden** hesaplanır; seans yönü hedefi seçmez, yalnız `headline` olarak
hangi yanın öne çıkarılacağını söyler (NEUTRAL iken hiçbiri — yön belirsizken
"şu seviyeyi kırar" demek uydurma olurdu; arayüz kuralı korunur). Eski akışta
hedef yöne göre **tek** seçiliyordu; okuyucu karşı yandaki seviyenin ne kadar
güvende olduğunu hiç görmüyordu.

Hedef çözümü yan başına üç basamak: (1) `Levels`'ın en yakın bölgesi (kimlikle;
test edilen bölgeleri o motor zaten dışlar, burada yeniden türetilmez),
(2) yoksa pivot merdiveninin `nearest_up` / `nearest_down` seviyesi — hiç test
edilmemiş bir çizgi olduğu için `fallback=True`, sönüm 1 ve `UNTESTED_LEVEL`
notu, (3) o da yoksa `NO_TARGET_ABOVE` / `NO_TARGET_BELOW`.

Cebir `frontend/src/domain/momentum/breakPotential.ts`'ten ölçülüp taşındı ve
iki ölçülmüş hata korunarak genişletildi:

    reach    = min(1, beklenen_hareket / uzaklık)
    push     = w_s · f_dir · seans_gücü/100 + w_d · günlük_itiş
    raw      = sqrt(reach · push)
    strength = round(100 · raw · sönüm),  sönüm = 1 − level_damping · bölge_gücü/100

* **Ulaşma 1'de doyurulur.** Seviyenin dibinde olmak onu kırmak değildir; ham
  oran 0,2 sigma yakınlıkta 88'e fırlıyor ve her şey STRONG çıkıyordu (ölçüldü).
* **Geometrik ortalama**: ulaşmak VE itilmek ikisi birden gerekir; biri sıfırsa
  sonuç sıfır. **Taban yok** — momentum 0 iken 0 verilir, "en az 10" gibi bir
  döşeme yoktur; döşeme "görüş yok"u "zayıf görüş" diye okuturdu.
* **Karşı yön cezası** (`opposed_factor`): seans aşağı iterken yukarı kırılım
  gücü seans katkısının çeyreğini alır. Günlük itiş de o yana karşıysa push en
  çok 0,25·0,6 = 0,15 olur, yani karşı yönde STRONG etiketi cebirsel olarak
  **imkânsızdır** (√0,15 ≈ 0,39); test bunu ızgarada doğrular.
* **Günlük itiş yöne bağlı**: skor 50'nin üstündeyse yalnız yukarı yanı iter,
  altındaysa yalnız aşağı yanı; `daily_span` puanda doyurur (50 + 25 = 75 tam
  itiş). Seans yokken ağırlık tamamen günlüğe kayar (0, 1) ve beklenen hareket
  ATR·√(ufuk) olur (`next_daily_bar` çerçevesi); seans varken seansın kalanında
  beklenen hareket (`session_remaining`). İkisi karıştırılmaz, çerçeve yanıtta
  yazılıdır.
* **Sönüm**: test edilmiş, güçlü bir bölgeyi kırmak zayıf bir çizgiyi geçmekten
  zordur; bölge gücü kırılım gücünü kısar. Pivot yedeğinde güç bilinmediği için
  sönüm 1'dir — bilinmeyeni 0 saymak yedek seviyeyi en kolay kırılan gösterirdi.
* Etiket yuvarlanmış sayıdan değil skorun kendisinden kesilir (1/3 ve 2/3 tam
  sayı değil; yuvarlama eşiği bir puan kaydırırdı). Etiketler WEAK / MODERATE /
  STRONG — eski `MEDIUM` adı kalktı, `levels.py` ile aynı sözlük.

Bütün büyüklükler oran: referans, hedefler, ATR ve beklenen hareket aynı çarpanla
ölçeklenince strength, etiket ve yüzde uzaklıklar değişmez (spot ↔ vadeli farkı
sadeleşir; test sabitler). Sayı bir **olasılık değildir** (`NOT_A_PROBABILITY`):
kalibre edilmemiş bir sıralama ölçüsüdür, "%47 ihtimalle kırar" diye okunmaz.

Eski davranış bir yapılandırmadır: `weight_session=1, weight_daily=0,
level_damping=0` ile canlı fixture (NEUTRAL, güç 22) ulaşılabilir bir hedefte
√0,22 = 0,469 → 47 verir; eski servis ve arayüz aynı sayıyı üretiyordu.
Saf, belirlenimci, numpy yok.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from .levels import Levels
from .momentum_daily import MIDPOINT, STATUS_OK as MOMENTUM_OK, MomentumDaily
from .pivots import ROLE_NEAREST_DOWN, ROLE_NEAREST_UP, Ladder

STATUS_OK = "OK"
STATUS_FLAT_MARKET = "FLAT_MARKET"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
NO_TARGET_ABOVE = "NO_TARGET_ABOVE"
NO_TARGET_BELOW = "NO_TARGET_BELOW"

SIDE_UP = "up"
SIDE_DOWN = "down"

DIRECTION_UP = "UP"
DIRECTION_DOWN = "DOWN"
DIRECTION_NEUTRAL = "NEUTRAL"
_DIRECTIONS = frozenset({DIRECTION_UP, DIRECTION_DOWN, DIRECTION_NEUTRAL})
# Yanın "kendi" seans yönü: bu ya da NEUTRAL ise ceza yok.
_SIDE_DIRECTION = {SIDE_UP: DIRECTION_UP, SIDE_DOWN: DIRECTION_DOWN}

FRAME_SESSION_REMAINING = "session_remaining"
FRAME_NEXT_DAILY_BAR = "next_daily_bar"

LABEL_STRONG = "STRONG"
LABEL_MODERATE = "MODERATE"
LABEL_WEAK = "WEAK"

NOTE_NOT_A_PROBABILITY = "NOT_A_PROBABILITY"
NOTE_UNTESTED_LEVEL = "UNTESTED_LEVEL"
NOTE_NO_EXPECTED_MOVE = "NO_EXPECTED_MOVE"

WEIGHT_TOLERANCE = 1e-9
_UNIT_INTERVAL_FIELDS = ("weight_session", "weight_daily", "opposed_factor",
                         "level_damping", "moderate", "strong")


@dataclass(frozen=True)
class BreakoutParams:
    """Ağırlıklar editoryal tercih, eşik değil: seans itişi "şu an ne oluyor"u,
    günlük itiş "haftalardır ne oluyor"u ölçer; ikisi 1'e toplanır. `daily_span`
    günlük skorun orta noktadan kaç puan uzakta tam itiş sayıldığı;
    `daily_horizon_bars` seans yokken beklenen hareketin ATR·√n ufku."""

    weight_session: float = 0.6
    weight_daily: float = 0.4
    opposed_factor: float = 0.25
    daily_span: float = 25.0
    level_damping: float = 0.5
    daily_horizon_bars: int = 1
    moderate: float = 1 / 3
    strong: float = 2 / 3

    def __post_init__(self) -> None:
        for name in _UNIT_INTERVAL_FIELDS:
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not 0.0 <= value <= 1.0):
                raise ValueError(f"{name} [0, 1] aralığında olmalı, {value!r} verildi")
        total = self.weight_session + self.weight_daily
        if abs(total - 1.0) > WEIGHT_TOLERANCE:
            raise ValueError(f"weight_session + weight_daily 1 olmalı, toplam {total!r}")
        if (isinstance(self.daily_span, bool) or not isinstance(self.daily_span, (int, float))
                or not math.isfinite(self.daily_span) or self.daily_span <= 0.0):
            raise ValueError(f"daily_span pozitif ve sonlu olmalı, {self.daily_span!r} verildi")
        if (isinstance(self.daily_horizon_bars, bool) or not isinstance(self.daily_horizon_bars, int)
                or self.daily_horizon_bars < 1):
            raise ValueError(f"daily_horizon_bars en az 1 olan tam sayı olmalı, "
                             f"{self.daily_horizon_bars!r} verildi")
        if self.moderate > self.strong:
            raise ValueError("moderate eşiği strong eşiğini aşamaz")


@dataclass(frozen=True)
class BreakoutTarget:
    """`zone_id` yalnız `Levels` bölgesinde; pivot yedeğinde None ve
    `fallback=True`. `value` bölgede orta nokta, merdivende seviyenin kendisi."""

    zone_id: str | None
    name: str
    value: float
    zone_strength: int | None
    fallback: bool


@dataclass(frozen=True)
class BreakoutSide:
    """Bir yanın raporu. `distance_pct` işaretli (+ yukarı / − aşağı), diğer
    uzaklıklar mutlak. `components`: direction_factor, session, daily, raw,
    score — skor 0–1, etiketin kesildiği sayı."""

    status: str
    target: BreakoutTarget | None
    distance_usd: float | None
    distance_pct: float | None
    distance_atr: float | None
    distance_sigma: float | None
    reach: float | None
    push: float | None
    damping: float | None
    components: dict[str, float]
    strength: int | None
    label: str | None
    note: str | None


@dataclass(frozen=True)
class Breakout:
    status: str
    note: str
    headline: str | None
    session_direction: str | None
    session_strength: int | None
    daily_direction: str | None
    daily_score: int | None
    expected_move: float | None
    expected_move_frame: str | None
    expected_move_pct: float | None
    weights: dict[str, float]
    up: BreakoutSide
    down: BreakoutSide


@dataclass(frozen=True)
class _SessionView:
    direction: str
    strength: float          # 0–100, kırpılı
    expected_move: float     # ≥ 0, referansla aynı fiyat çerçevesinde
    sigma_pct: float | None  # mum getirisi sapması, oran


# --- girdi okuma ---------------------------------------------------------------

def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _read_session(session: Mapping | None) -> _SessionView | None:
    """Seans bloğu ancak yön, güç ve `session.expected_move` üçü de okunuyorsa
    kullanılır. Yarım bir seans yanıtıyla hesap uydurmaktansa blok yok sayılır
    ve çerçeve açıkça günlüğe (`next_daily_bar`) çevrilir."""
    if not isinstance(session, Mapping):
        return None
    direction = session.get("direction")
    strength = _finite(session.get("strength"))
    inner = session.get("session")
    if direction not in _DIRECTIONS or strength is None or not isinstance(inner, Mapping):
        return None
    expected = _finite(inner.get("expected_move"))
    if expected is None or expected < 0.0:
        return None
    sigma = _finite(inner.get("volatility_pct"))
    sigma_pct = sigma / 100.0 if sigma is not None and sigma > 0.0 else None
    return _SessionView(str(direction), min(100.0, max(0.0, strength)), expected, sigma_pct)


def _zone_target(levels: Levels | None, zone_id: str | None) -> BreakoutTarget | None:
    if levels is None or zone_id is None:
        return None
    zone = next((z for z in levels.zones if z.id == zone_id), None)
    if zone is None:
        return None
    return BreakoutTarget(zone_id=zone.id, name=zone.name, value=zone.mid,
                          zone_strength=zone.strength, fallback=False)


def _ladder_target(ladder: Ladder | None, role: str, name: str | None) -> BreakoutTarget | None:
    if ladder is None or name is None:
        return None
    # Önce rol (tam indeks), sonra ad: merdivende aynı ad iki kez geçebilir.
    item = (next((i for i in ladder.items if i.role == role), None)
            or next((i for i in ladder.items if i.name == name), None))
    if item is None:
        return None
    return BreakoutTarget(zone_id=None, name=item.name, value=item.value,
                          zone_strength=None, fallback=True)


def _resolve_target(side: str, reference: float, levels: Levels | None,
                    ladder: Ladder | None) -> BreakoutTarget | None:
    """Bölge → pivot yedeği → yok. Yanlış yanda kalan aday (bozuk girdi)
    atlanır; uzaklık sıfır ya da ters işaretliyken "kırma" sorusu anlamsız."""
    if side == SIDE_UP:
        candidates = (_zone_target(levels, levels.nearest_resistance if levels else None),
                      _ladder_target(ladder, ROLE_NEAREST_UP, ladder.nearest_up if ladder else None))
    else:
        candidates = (_zone_target(levels, levels.nearest_support if levels else None),
                      _ladder_target(ladder, ROLE_NEAREST_DOWN, ladder.nearest_down if ladder else None))
    for target in candidates:
        if target is None:
            continue
        delta = target.value - reference
        if delta > 0.0 if side == SIDE_UP else delta < 0.0:
            return target
    return None


# --- hesap ---------------------------------------------------------------------

def _empty_side(status: str) -> BreakoutSide:
    return BreakoutSide(status=status, target=None, distance_usd=None, distance_pct=None,
                        distance_atr=None, distance_sigma=None, reach=None, push=None,
                        damping=None, components={}, strength=None, label=None, note=None)


def _empty(status: str) -> Breakout:
    side = _empty_side(status)
    return Breakout(status=status, note=NOTE_NOT_A_PROBABILITY, headline=None,
                    session_direction=None, session_strength=None, daily_direction=None,
                    daily_score=None, expected_move=None, expected_move_frame=None,
                    expected_move_pct=None, weights={}, up=side, down=side)


def label_for(score: float, params: BreakoutParams = BreakoutParams()) -> str:
    """0–1 skorun etiketi; eşikler kapalı alt sınır (skor ≥ eşik)."""
    if score >= params.strong:
        return LABEL_STRONG
    if score >= params.moderate:
        return LABEL_MODERATE
    return LABEL_WEAK


def _side(side: str, reference: float, unit: float, target: BreakoutTarget | None,
          expected_move: float, view: _SessionView | None, daily_score: int | None,
          weights: dict[str, float], params: BreakoutParams) -> BreakoutSide:
    if target is None:
        return _empty_side(NO_TARGET_ABOVE if side == SIDE_UP else NO_TARGET_BELOW)
    delta = target.value - reference
    distance = abs(delta)
    reach = min(1.0, expected_move / distance)

    if view is None:
        direction_factor, session_push = 1.0, 0.0
    else:
        opposed = view.direction not in (DIRECTION_NEUTRAL, _SIDE_DIRECTION[side])
        direction_factor = params.opposed_factor if opposed else 1.0
        session_push = direction_factor * view.strength / 100.0

    if daily_score is None:
        daily_push = 0.0
    else:
        signed = (daily_score - MIDPOINT) if side == SIDE_UP else (MIDPOINT - daily_score)
        daily_push = min(1.0, max(0.0, signed / params.daily_span))

    push = weights["session"] * session_push + weights["daily"] * daily_push
    raw = math.sqrt(reach * push)
    damping = 1.0
    if target.zone_strength is not None:
        damping = max(0.0, 1.0 - params.level_damping * target.zone_strength / 100.0)
    score = raw * damping

    if expected_move <= 0.0:
        note = NOTE_NO_EXPECTED_MOVE
    elif target.fallback:
        note = NOTE_UNTESTED_LEVEL
    else:
        note = None
    sigma = view.sigma_pct if view is not None else None
    return BreakoutSide(
        status=STATUS_OK, target=target, distance_usd=distance, distance_pct=delta / reference,
        distance_atr=distance / unit,
        distance_sigma=distance / (reference * sigma) if sigma is not None else None,
        reach=reach, push=push, damping=damping,
        components={"direction_factor": direction_factor, "session": session_push,
                    "daily": daily_push, "raw": raw, "score": score},
        strength=int(round(100.0 * score)), label=label_for(score, params), note=note)


def analyze_breakout(*, reference: float | None, atr: float | None, levels: Levels | None,
                     pivot_ladder: Ladder | None, session: Mapping | None,
                     momentum_daily: MomentumDaily | None,
                     params: BreakoutParams = BreakoutParams()) -> Breakout:
    """İki yanın kırılım raporu. `reference`, `levels`, `pivot_ladder` ve seansın
    `expected_move`'u **aynı fiyat çerçevesinde** olmalı (`reference.py` bunu
    seçer); `atr` günlük ATR. Referans yoksa INSUFFICIENT_DATA, ATR yok ya da
    sıfırsa FLAT_MARKET — ikisinde de hiçbir şey hesaplanmaz."""
    ref = _finite(reference)
    if ref is None or ref <= 0.0:
        return _empty(STATUS_INSUFFICIENT_DATA)
    unit = _finite(atr)
    if unit is None or unit <= 0.0:
        return _empty(STATUS_FLAT_MARKET)

    view = _read_session(session)
    if view is not None:
        expected_move, frame = view.expected_move, FRAME_SESSION_REMAINING
        weights = {"session": params.weight_session, "daily": params.weight_daily}
    else:
        expected_move, frame = unit * math.sqrt(params.daily_horizon_bars), FRAME_NEXT_DAILY_BAR
        weights = {"session": 0.0, "daily": 1.0}

    daily_ok = (momentum_daily is not None and momentum_daily.status == MOMENTUM_OK
                and momentum_daily.score is not None)
    daily_score = momentum_daily.score if daily_ok else None
    daily_direction = momentum_daily.direction if daily_ok else None

    sides = {}
    for side in (SIDE_UP, SIDE_DOWN):
        target = _resolve_target(side, ref, levels, pivot_ladder)
        sides[side] = _side(side, ref, unit, target, expected_move, view, daily_score, weights, params)

    headline = None
    if view is not None and view.direction == DIRECTION_UP:
        headline = SIDE_UP
    elif view is not None and view.direction == DIRECTION_DOWN:
        headline = SIDE_DOWN

    return Breakout(
        status=STATUS_OK, note=NOTE_NOT_A_PROBABILITY, headline=headline,
        session_direction=view.direction if view is not None else None,
        session_strength=int(round(view.strength)) if view is not None else None,
        daily_direction=daily_direction, daily_score=daily_score,
        expected_move=expected_move, expected_move_frame=frame, expected_move_pct=expected_move / ref,
        weights=weights, up=sides[SIDE_UP], down=sides[SIDE_DOWN])
