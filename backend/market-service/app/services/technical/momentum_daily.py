"""Günlük mumlardan bileşik momentum skoru (0–100), walk-forward.

Gün içi blok (`session.py`) 5 dakikalık mumlarla "bu seans ilk seviyeyi kırmaya
yeter mi" sorusuna cevap verir. Bu modül aynı felsefeyi **günlük** mumlara
uygular ve başka bir soru sorar: *son haftaların hareketi ne kadar tek yönlü ve
ne kadar kararlı?* İkisi ayrı bloklardır; birbirini içe aktarmazlar.

Paylaşılan felsefe:

* Her bileşen kendi ölçeğinden arındırılır ve **oynaklık biriminde** işaretli
  bir sayı olur (σ, ATR ya da göstergenin doğal ölçeği). Aynı 30 dolarlık
  hareket sakin piyasada güçlü, çalkantılı piyasada zayıf okunur; fiyatın
  seviyesi (1.800 ya da 4.500 $) sonucu değiştirmez — bütün bileşenler oran.
* Isınmadaki bileşen (None) **düşürülür**, ağırlığı kalanlara dağıtılır.
  Sıfır yazmak "görüş yok"u "nötr görüş" diye okurdu ve skoru 50'ye çekerdi.
* Skor bileşik sinyalin büyüklüğüdür; **uyum** (agreement) bileşenlerin ne
  kadar hemfikir olduğu. İkisi ayrı sorular: sıfır çevresinde kümelenmiş altı
  bileşen ile +3 / −3 diye çekişen altı bileşen aynı skoru verir, uyum ayırır.
  NEUTRAL etikette uyum düşükse "CONFLICTING" notu düşülür: piyasa durgun
  değil, göstergeler çelişiyor.

Walk-forward: skor **serisi** tek nedensel geçişte hesaplanır; t'deki skor
yalnız t ve öncesindeki mumları görür (bütün gösterge serileri nedensel, σ
kayan pencere). Delta / ivme / trend etiketleri aynı seriden okunur ve
`score_series(bars[:t])[t-1] == score_series(bars)[t-1]` her t için tutar.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from app.services.technical.indicators import (
    Bar, IndicatorParams, Series, adx, atr, macd, rsi, sma,
)

# Bölme koruması. σ log getiriden gelir (boyutsuz), ATR fiyat biriminde; ATR
# için eşik kapanışa göre ölçeklenir.
EPS = 1e-12
WEIGHT_TOLERANCE = 1e-9

STATUS_OK = "OK"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STATUS_FLAT_MARKET = "FLAT_MARKET"

DIRECTION_UP = "UP"
DIRECTION_DOWN = "DOWN"
DIRECTION_NEUTRAL = "NEUTRAL"

STRENGTH_STRONG = "STRONG"
STRENGTH_MODERATE = "MODERATE"
STRENGTH_WEAK = "WEAK"

TREND_STRENGTHENING = "STRENGTHENING"
TREND_WEAKENING = "WEAKENING"
TREND_STABLE = "STABLE"

NOTE_CONFLICTING = "CONFLICTING"

# Skorun orta noktası: `50 + 50·tanh(z / z_scale)` z = 0'da tam buraya düşer.
MIDPOINT = 50
# Wilder RSI'ın nötr değeri; (RSI − 50) merkezleme bunu kullanır.
RSI_NEUTRAL = 50.0

COMPONENTS = ("velocity", "drift", "rsi", "macd", "adx", "ma")


def _require_positive_int(value: int, name: str, minimum: int = 1) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{name} en az {minimum} olan bir tam sayı olmalı, {value!r} verildi")


def _require_positive(value: float, name: str) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} pozitif ve sonlu olmalı, {value!r} verildi")


@dataclass(frozen=True)
class MomentumParams:
    """Tasarım §6.2 sabitleri. Ağırlıklar eşik değil **editoryal tercih**: hız
    ve sürüklenme fiyatın kendisini ölçer (asıl soru), osilatörler teyit eder.
    Sabit hızlı bir trendde MACD histogramı sıfıra yakınsar (EMA'lar aynı
    eğime oturur); ona ağır ağırlık vermek düz trendi zayıf gösterirdi."""

    velocity_days: int = 10
    drift_days: int = 20
    sigma_days: int = 20
    ma_period: int = 50
    adx_cap: float = 50.0
    adx_scale: float = 25.0
    rsi_scale: float = 10.0
    ma_clip: float = 3.0
    weights: tuple[tuple[str, float], ...] = (
        ("velocity", 0.25), ("drift", 0.20), ("rsi", 0.15),
        ("macd", 0.15), ("adx", 0.15), ("ma", 0.10),
    )
    z_scale: float = 2.0
    up: int = 60
    down: int = 40
    moderate: int = 10
    strong: int = 25
    trend_delta: int = 3
    trend_days: int = 3
    history: int = 30
    conflicting_agreement: float = 0.5
    min_bars: int = 35

    def __post_init__(self) -> None:
        names = [name for name, _ in self.weights]
        unknown = sorted(set(names) - set(COMPONENTS))
        if unknown:
            raise ValueError(f"bilinmeyen bileşen ağırlığı: {unknown}")
        if len(set(names)) != len(names):
            raise ValueError("bir bileşen iki kez ağırlıklandırılmış")
        if any(weight < 0.0 for _, weight in self.weights):
            raise ValueError("ağırlık negatif olamaz")
        total = math.fsum(weight for _, weight in self.weights)
        if abs(total - 1.0) > WEIGHT_TOLERANCE:
            raise ValueError(f"ağırlıklar 1'e toplanmalı, toplam {total!r}")
        for name in ("velocity_days", "drift_days", "ma_period", "trend_days",
                     "history", "min_bars"):
            _require_positive_int(getattr(self, name), name)
        # ddof = 1: tek getiriden sapma tanımsız.
        _require_positive_int(self.sigma_days, "sigma_days", minimum=2)
        for name in ("z_scale", "adx_scale", "rsi_scale", "ma_clip"):
            _require_positive(getattr(self, name), name)
        if self.down >= self.up:
            raise ValueError("down eşiği up eşiğinden küçük olmalı")

    def weight_map(self) -> dict[str, float]:
        return dict(self.weights)


@dataclass(frozen=True)
class MomentumDaily:
    status: str  # OK | INSUFFICIENT_DATA | FLAT_MARKET
    date: date | None
    score: int | None
    direction: str | None
    strength: str | None
    trend: str | None
    agreement: float | None
    z: float | None
    delta: int | None
    acceleration: int | None
    note: str | None
    components: dict[str, float]
    weights: dict[str, float]
    z_scale: float
    history: tuple[int, ...]
    sigma: float | None
    atr: float | None


@dataclass(frozen=True)
class _Frame:
    """Tek indeksin ham sonucu; etiketler seri kurulduktan sonra eklenir."""

    status: str
    components: dict[str, float] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    z: float | None = None
    agreement: float | None = None
    score: int | None = None
    sigma: float | None = None
    atr: float | None = None


# --- yapı taşları ---------------------------------------------------------------

def _log_returns(closes: Sequence[float]) -> list[float | None]:
    """r_t = ln(C_t / C_{t−1}); ilk mumda ve pozitif olmayan fiyatta None."""
    out: list[float | None] = [None]
    for previous, current in zip(closes, closes[1:]):
        out.append(math.log(current / previous) if previous > 0.0 and current > 0.0 else None)
    return out


def _rolling_sigma(returns: Sequence[float | None], window: int) -> Series:
    """Son `window` log getirinin örneklem sapması (ddof = 1), t'de t dahil.

    Pencere sabit olduğu için iki geçişli hesap yine O(n). Kayan toplam
    kullanılmadı: `0,1 + 0,2 − 0,1 − 0,2 ≠ 0`; hareketli bir dönemin ardından
    gelen düz kuyrukta toplamlar sıfıra dönmez, σ ~1e−9 kalır ve FLAT_MARKET
    korumasını atlatır. `fsum` ile düz pencere **tam olarak** sıfır verir
    (`indicators.cci` aynı sebeple aynı yolu seçti)."""
    out: Series = [None] * len(returns)
    for index in range(window, len(returns)):
        block = returns[index - window + 1:index + 1]
        if any(value is None for value in block):
            continue
        values = [value for value in block if value is not None]
        mean = math.fsum(values) / window
        variance = math.fsum((value - mean) ** 2 for value in values) / (window - 1)
        out[index] = math.sqrt(max(variance, 0.0))
    return out


def _clamp(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def _sign(value: float) -> int:
    return 1 if value > 0.0 else -1 if value < 0.0 else 0


def _components_at(index: int, closes: Sequence[float], sigma: float | None, atr_value: float | None,
                   rsi_value: float | None, histogram: float | None, adx_value: float | None,
                   plus_di: float | None, minus_di: float | None, ma_value: float | None,
                   params: MomentumParams) -> dict[str, float]:
    """t'deki mevcut bileşenler; ısınmadaki bileşen sözlükte hiç yer almaz."""
    close = closes[index]
    raw: dict[str, float] = {}
    if sigma is not None and close > 0.0:
        # Hız ve sürüklenme: n günlük log getiri, aynı pencerede rastgele
        # yürüyüşün beklenen yayılımına (σ·√n) bölünür. Uzun pencere n ile
        # birikir, gürültü √n ile büyür; sürüklenme bu yüzden aynı trendde
        # hızdan daha güçlü bir sinyaldir (gün içi blokla aynı gerekçe).
        for name, days in (("velocity", params.velocity_days), ("drift", params.drift_days)):
            if index >= days and closes[index - days] > 0.0:
                raw[name] = math.log(close / closes[index - days]) / (sigma * math.sqrt(days))
    if rsi_value is not None:
        raw["rsi"] = (rsi_value - RSI_NEUTRAL) / params.rsi_scale
    if atr_value is not None:
        # Histogram ve ortalamadan uzaklık fiyat biriminde; ATR'ye bölmek onları
        # "kaç günlük tipik hareket" ölçeğine taşır ve seviyeden bağımsızlaştırır.
        if histogram is not None:
            raw["macd"] = histogram / atr_value
        if ma_value is not None:
            raw["ma"] = _clamp((close - ma_value) / atr_value, params.ma_clip)
    if adx_value is not None and plus_di is not None and minus_di is not None:
        # ADX yönsüzdür; yön DI farkından gelir. 50'de kırpma: ADX 50 üstü zaten
        # "çok güçlü trend"dir, daha yükseği tek bir bileşenin skoru ele
        # geçirmesine yarardı.
        raw["adx"] = _sign(plus_di - minus_di) * min(adx_value, params.adx_cap) / params.adx_scale
    # Çıktı sırası ağırlık tablosunun sırası; okunabilirlik için.
    return {name: raw[name] for name, _ in params.weights if name in raw}


def _composite(components: dict[str, float], params: MomentumParams
               ) -> tuple[dict[str, float], float, float, int] | None:
    """(yeniden dağıtılmış ağırlıklar, z, uyum, skor); ağırlık kalmadıysa None."""
    table = params.weight_map()
    present = {name: table[name] for name in components}
    total = math.fsum(present.values())
    if total <= 0.0:
        return None
    weights = {name: weight / total for name, weight in present.items()}
    z = math.fsum(weights[name] * components[name] for name in weights)
    dispersion = math.sqrt(max(0.0, math.fsum(
        weights[name] * (components[name] - z) ** 2 for name in weights)))
    # Uyum: bileşik sinyalin, bileşenlerin etrafındaki dağılımına oranı.
    # Hepsi sıfırsa tanımsız değil 0: hemfikir olunacak bir şey yok.
    magnitude = abs(z)
    agreement = 0.0 if magnitude + dispersion <= EPS else magnitude / (magnitude + dispersion)
    score = int(round(MIDPOINT + MIDPOINT * math.tanh(z / params.z_scale)))
    return weights, z, agreement, score


def _frames(bars: Sequence[Bar], params: MomentumParams, indicator_params: IndicatorParams
            ) -> list[_Frame]:
    """Her indeks için ham sonuç, tek nedensel geçişte. Gösterge serileri
    girdiyle hizalı ve ısınma boyunca None; hepsi yalnız geçmişe bakar."""
    closes = [bar.close for bar in bars]
    sigma_line = _rolling_sigma(_log_returns(closes), params.sigma_days)
    atr_line = atr(bars, indicator_params.atr_period)
    rsi_line = rsi(closes, indicator_params.rsi_period)
    _, _, histogram_line = macd(closes, indicator_params.macd_fast, indicator_params.macd_slow,
                                indicator_params.macd_signal)
    adx_line, plus_line, minus_line = adx(bars, indicator_params.adx_period)
    ma_line = sma(closes, params.ma_period)

    frames: list[_Frame] = []
    for index in range(len(bars)):
        sigma = sigma_line[index]
        atr_value = atr_line[index]
        if index + 1 < params.min_bars:
            frames.append(_Frame(STATUS_INSUFFICIENT_DATA, sigma=sigma, atr=atr_value))
            continue
        # σ ya da ATR sıfırsa bölme tanımsız; "nötr" değil "ölçülemez".
        flat = (sigma is not None and sigma <= EPS) or (
            atr_value is not None and atr_value <= EPS * max(abs(closes[index]), 1.0))
        if flat:
            frames.append(_Frame(STATUS_FLAT_MARKET, sigma=sigma, atr=atr_value))
            continue
        components = _components_at(
            index, closes, sigma, atr_value, rsi_line[index], histogram_line[index],
            adx_line[index], plus_line[index], minus_line[index], ma_line[index], params)
        composite = _composite(components, params)
        if composite is None:
            frames.append(_Frame(STATUS_INSUFFICIENT_DATA, sigma=sigma, atr=atr_value))
            continue
        weights, z, agreement, score = composite
        frames.append(_Frame(STATUS_OK, components, weights, z, agreement, score, sigma, atr_value))
    return frames


# --- etiketler ------------------------------------------------------------------

def label_direction(score: int, params: MomentumParams = MomentumParams()) -> str:
    if score >= params.up:
        return DIRECTION_UP
    if score <= params.down:
        return DIRECTION_DOWN
    return DIRECTION_NEUTRAL


def label_strength(score: int, params: MomentumParams = MomentumParams()) -> str:
    distance = abs(score - MIDPOINT)
    if distance >= params.strong:
        return STRENGTH_STRONG
    if distance >= params.moderate:
        return STRENGTH_MODERATE
    return STRENGTH_WEAK


def label_trend(current: int | None, earlier: int | None,
                params: MomentumParams = MomentumParams()) -> str | None:
    """Skorun orta noktadan uzaklığı `trend_days` önceye göre büyüdü mü?
    Yönden bağımsız: 30 → 20 de güçlenmedir (düşüş momentumu artıyor)."""
    if current is None or earlier is None:
        return None
    change = abs(current - MIDPOINT) - abs(earlier - MIDPOINT)
    if change >= params.trend_delta:
        return TREND_STRENGTHENING
    if change <= -params.trend_delta:
        return TREND_WEAKENING
    return TREND_STABLE


def label_note(direction: str, agreement: float,
               params: MomentumParams = MomentumParams()) -> str | None:
    """NEUTRAL iki şey olabilir: durgun piyasa ya da çekişen göstergeler.
    Uyum düşükse ikincisi; okuyucuya "görüş yok" değil "görüşler çelişiyor" denir."""
    if direction == DIRECTION_NEUTRAL and agreement < params.conflicting_agreement:
        return NOTE_CONFLICTING
    return None


# --- açık API -------------------------------------------------------------------

def score_series(bars: Sequence[Bar], params: MomentumParams = MomentumParams(),
                 indicator_params: IndicatorParams = IndicatorParams()) -> list[int | None]:
    """Girdiyle aynı uzunlukta skor serisi; ölçülemeyen indekste None."""
    return [frame.score for frame in _frames(bars, params, indicator_params)]


def _empty(status: str, as_of: date | None, params: MomentumParams, history: tuple[int, ...],
           sigma: float | None, atr_value: float | None) -> MomentumDaily:
    return MomentumDaily(
        status=status, date=as_of, score=None, direction=None, strength=None, trend=None,
        agreement=None, z=None, delta=None, acceleration=None, note=None, components={},
        weights={}, z_scale=params.z_scale, history=history, sigma=sigma, atr=atr_value)


def momentum_daily(bars: Sequence[Bar], params: MomentumParams = MomentumParams(),
                   indicator_params: IndicatorParams = IndicatorParams()) -> MomentumDaily:
    """Son mumun bileşik momentum raporu; `date` son mumun tarihi (varsa).

    Delta, ivme ve trend skor **serisinden** okunur: bugünün skoru dünkü ve
    üç gün önceki skorla karşılaştırılır, her biri kendi gününün verisiyle
    hesaplanmıştır. `history` son `params.history` günün skorları (ölçülemeyen
    günler atlanır); hiçbir alan geleceğe bakmaz.
    """
    as_of = getattr(bars[-1], "date", None) if bars else None
    frames = _frames(bars, params, indicator_params)
    if not frames:
        return _empty(STATUS_INSUFFICIENT_DATA, as_of, params, (), None, None)
    scores = [frame.score for frame in frames]
    history = tuple(score for score in scores[-params.history:] if score is not None)
    last = frames[-1]
    if last.status != STATUS_OK or last.score is None or last.agreement is None:
        return _empty(last.status, as_of, params, history, last.sigma, last.atr)

    score = last.score
    previous = scores[-2] if len(scores) >= 2 else None
    before = scores[-3] if len(scores) >= 3 else None
    delta = None if previous is None else score - previous
    prior_delta = None if previous is None or before is None else previous - before
    acceleration = None if delta is None or prior_delta is None else delta - prior_delta
    earlier = scores[-1 - params.trend_days] if len(scores) > params.trend_days else None
    direction = label_direction(score, params)

    return MomentumDaily(
        status=STATUS_OK, date=as_of, score=score, direction=direction,
        strength=label_strength(score, params), trend=label_trend(score, earlier, params),
        agreement=last.agreement, z=last.z, delta=delta, acceleration=acceleration,
        note=label_note(direction, last.agreement, params), components=dict(last.components),
        weights=dict(last.weights), z_scale=params.z_scale, history=history,
        sigma=last.sigma, atr=last.atr)
