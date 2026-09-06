"""Günlük mum üzerinde klasik teknik göstergeler — **Wilder standardında**.

Bu modül önceden tarayıcıda hesaplanan göstergelerin yerini alır. Oradaki
tanımlar standart dışıydı ve sayılar TradingView / StockCharts ile tutmuyordu:

* RSI Cutler biçimindeydi (basit ortalama) ve **düz seride 0** veriyordu — yani
  hiç hareket etmeyen piyasa "aşırı satım" okunuyordu. Wilder RSI'da her iki
  ortalama sıfırsa piyasa **nötr**dür (50); yalnız kayıp sıfırsa 100.
* ATR basit ortalamaydı; Wilder yumuşatması (`s = (s·(n−1) + x) / n`) sıçramayı
  daha yavaş unutur ve yayınlanmış referans değerleri onunla üretilir.
* ADX, DX'in basit ortalamasıydı; standart tanımda DX de Wilder ile yumuşatılır
  ve ilk değer `2n − 1` mum sonra çıkar (14 için 28. gün).

Tasarım kuralları:

* Seri fonksiyonları girdiyle **aynı uzunlukta** liste döner; ısınma boyunca
  `None`. Her indeks yalnız geçmiş değerlerden hesaplanır (ileri bakış yok).
* Tohum kuralları StockCharts çalışma sayfalarıyla aynıdır: EMA ilk `n` değerin
  basit ortalamasıyla, Wilder ortalaması da öyle başlar. Bu yüzden testlerdeki
  yayınlanmış RSI dizisi iki ondalığa kadar birebir tutar.
* Bölen sıfırken sonuç tanımsız değil **nötr**dür: RSI 50, stokastik 50,
  Williams −50, CCI 0, DX 0. Düz piyasa sinyal üretmemeli.
* Eşikler `IndicatorParams` içinde; kodda gömülü sihirli sayı yok.
* numpy yok; her gösterge tek geçişte (`O(n)`) ya da sabit pencereyle hesaplanır.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from statistics import median
from typing import Protocol

# Göreli sıfır eşiği. CCI'da pencere ortalaması kayan noktada verinin kendisinden
# bir ulp sapabiliyor; o zaman sapma da MAD da ~1e-16 olur ve `sapma / (0,015·MAD)`
# düz seride 66 verir. Sıfır kararı ölçekle orantılı verilir.
REL_EPS = 1e-12
CCI_SCALE = 0.015


@dataclass(frozen=True)
class IndicatorParams:
    rsi_period: int = 14
    atr_period: int = 14
    adx_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    stoch_k: int = 14
    stoch_d: int = 3
    williams_period: int = 14
    cci_period: int = 20
    roc_period: int = 12
    ma_periods: tuple[int, ...] = (5, 10, 20, 50, 100, 200)
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    stoch_overbought: float = 80.0
    stoch_oversold: float = 20.0
    williams_overbought: float = -20.0
    williams_oversold: float = -80.0
    cci_band: float = 100.0
    adx_trending: float = 25.0
    adx_weak: float = 20.0
    atr_high_ratio: float = 1.3
    atr_low_ratio: float = 0.7
    # ATR "yüksek/düşük" kararı için karşılaştırma tabanı: önceki ~100 günün
    # (yaklaşık beş ay) ATR medyanı. Ortalama değil medyan, çünkü tek bir
    # çalkantılı hafta tabanı yukarı çekip sonraki ayları "sakin" göstermesin.
    atr_median_window: int = 100


class Bar(Protocol):
    """Ördek tipli mum: `high`, `low`, `close` taşıyan her nesne kabul edilir."""

    high: float
    low: float
    close: float


class IndicatorState(str, Enum):
    OVERBOUGHT = "OVERBOUGHT"
    OVERSOLD = "OVERSOLD"
    NEUTRAL = "NEUTRAL"
    ABOVE_SIGNAL = "ABOVE_SIGNAL"
    BELOW_SIGNAL = "BELOW_SIGNAL"
    TRENDING = "TRENDING"
    WEAK_TREND = "WEAK_TREND"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    NORMAL_VOLATILITY = "NORMAL_VOLATILITY"
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    ABOVE = "ABOVE"
    BELOW = "BELOW"


@dataclass(frozen=True)
class IndicatorReading:
    key: str
    value: float | None
    extra: dict[str, float | None]
    state: IndicatorState | None


Series = list[float | None]


# --- yardımcılar --------------------------------------------------------------

def _check_period(period: int, name: str = "period") -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period < 1:
        raise ValueError(f"{name} pozitif tam sayı olmalı, {period!r} verildi")


def _pad(values: Sequence[float | None], offset: int, length: int) -> Series:
    """Hesaplanan kuyruğu `offset` kadar None ile öne uzatıp girdi boyuna hizalar."""
    out: Series = [None] * offset
    out.extend(values)
    if len(out) != length:
        raise AssertionError(f"seri hizası bozuk: {len(out)} != {length}")
    return out


def _valid_tail(series: Sequence[float | None]) -> tuple[int, list[float]]:
    """(ilk geçerli indeks, geçerli kuyruk). Isınma yapısı gereği geçerli
    değerler daima bitişik bir kuyruktur; sonrasında None yoktur."""
    for index, value in enumerate(series):
        if value is not None:
            tail = [v for v in series[index:] if v is not None]
            return index, tail
    return len(series), []


def _rolling_extreme(values: Sequence[float], period: int, better: Callable[[float, float], bool]) -> Series:
    """Kayan pencere uç değeri (monoton deque, `O(n)`). `better(a, b)` a'nın
    b'yi pencereden düşürdüğünü söyler (maks için `a >= b`)."""
    out: Series = [None] * len(values)
    window: deque[int] = deque()
    for index, value in enumerate(values):
        while window and better(value, values[window[-1]]):
            window.pop()
        window.append(index)
        if window[0] <= index - period:
            window.popleft()
        if index >= period - 1:
            out[index] = values[window[0]]
    return out


def _rolling_max(values: Sequence[float], period: int) -> Series:
    return _rolling_extreme(values, period, lambda a, b: a >= b)


def _rolling_min(values: Sequence[float], period: int) -> Series:
    return _rolling_extreme(values, period, lambda a, b: a <= b)


def _is_zero(value: float, scale: float) -> bool:
    return abs(value) <= REL_EPS * max(abs(scale), 1.0)


# --- temel yumuşatmalar -------------------------------------------------------

def sma(values: Sequence[float], period: int) -> Series:
    """Basit hareketli ortalama; ilk `period − 1` indeks None."""
    _check_period(period)
    out: Series = [None] * len(values)
    total = 0.0
    for index, value in enumerate(values):
        total += value
        if index >= period:
            total -= values[index - period]
        if index >= period - 1:
            out[index] = total / period
    return out


def ema(values: Sequence[float], period: int) -> Series:
    """Üstel ortalama. Tohum ilk `period` değerin SMA'sı, sonra `k = 2 / (n + 1)`.

    İlk değerden başlatmak (TradingView'ın yaptığı) ısınma boyunca farklı
    sayılar verir; StockCharts çalışma sayfaları SMA tohumunu kullanır ve
    referans dizilerimiz oradan geliyor."""
    _check_period(period)
    out: Series = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1)
    current = sum(values[:period]) / period
    out[period - 1] = current
    for index in range(period, len(values)):
        current = values[index] * k + current * (1.0 - k)
        out[index] = current
    return out


def wilder_smooth(values: Sequence[float], period: int) -> Series:
    """Wilder ortalaması: tohum ilk `n` değerin ortalaması, sonra
    `s = (s·(n − 1) + x) / n` — yani `α = 1/n` olan bir EMA."""
    _check_period(period)
    out: Series = [None] * len(values)
    if len(values) < period:
        return out
    current = sum(values[:period]) / period
    out[period - 1] = current
    for index in range(period, len(values)):
        current = (current * (period - 1) + values[index]) / period
        out[index] = current
    return out


# --- momentum osilatörleri ----------------------------------------------------

def rsi(closes: Sequence[float], period: int = 14) -> Series:
    """Wilder RSI. İlk değer `period` indeksinde (n değişim gerekir).

    Düz seri: kazanç da kayıp da 0 → **50**. Tarayıcıdaki eski Cutler sürümü
    burada 0 döndürüp piyasayı "aşırı satım" gösteriyordu; hareket yoksa
    görüş de yoktur. Kayıp 0, kazanç > 0 → 100 (bölme yapılmaz)."""
    _check_period(period)
    if len(closes) < 2:
        return [None] * len(closes)
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(closes, closes[1:]):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = wilder_smooth(gains, period)
    avg_loss = wilder_smooth(losses, period)
    out: Series = [None] * len(closes)
    for index, (gain, loss) in enumerate(zip(avg_gain, avg_loss), start=1):
        if gain is None or loss is None:
            continue
        if loss == 0.0:
            out[index] = 100.0 if gain > 0.0 else 50.0
        else:
            out[index] = 100.0 - 100.0 / (1.0 + gain / loss)
    return out


def stochastic(bars: Sequence[Bar], k_period: int = 14, d_period: int = 3) -> tuple[Series, Series]:
    """Hızlı stokastik: %K = 100·(c − LL)/(HH − LL), %D = SMA(%K, d).
    Aralık sıfırsa (HH == LL) %K = 50 — düz piyasa nötrdür."""
    _check_period(k_period, "k_period")
    _check_period(d_period, "d_period")
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    highest = _rolling_max(highs, k_period)
    lowest = _rolling_min(lows, k_period)
    k_line: Series = [None] * len(bars)
    for index, bar in enumerate(bars):
        hh, ll = highest[index], lowest[index]
        if hh is None or ll is None:
            continue
        spread = hh - ll
        k_line[index] = 50.0 if spread == 0.0 else 100.0 * (bar.close - ll) / spread
    offset, tail = _valid_tail(k_line)
    d_line = _pad(sma(tail, d_period), offset, len(bars))
    return k_line, d_line


def williams_r(bars: Sequence[Bar], period: int = 14) -> Series:
    """Williams %R = −100·(HH − c)/(HH − LL); aralık sıfırsa −50 (nötr)."""
    _check_period(period)
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    highest = _rolling_max(highs, period)
    lowest = _rolling_min(lows, period)
    out: Series = [None] * len(bars)
    for index, bar in enumerate(bars):
        hh, ll = highest[index], lowest[index]
        if hh is None or ll is None:
            continue
        spread = hh - ll
        out[index] = -50.0 if spread == 0.0 else -100.0 * (hh - bar.close) / spread
    return out


def cci(bars: Sequence[Bar], period: int = 20) -> Series:
    """CCI = (TP − SMA(TP)) / (0,015·MAD), TP = (h + l + c)/3.

    MAD pencere ortalamasına göre mutlak sapmadır ve artımlı güncellenemez;
    pencere sabit olduğu için maliyet yine `O(n·period)`, yani doğrusal.
    Ortalama ve MAD aynı pencerede `fsum` ile alınır; kayan toplam kullanılsaydı
    düz seride sapma sıfır yerine bir ulp çıkıyor ve CCI 0 yerine 66 oluyordu.
    MAD (göreli) sıfırsa CCI 0."""
    _check_period(period)
    typical = [(bar.high + bar.low + bar.close) / 3.0 for bar in bars]
    out: Series = [None] * len(bars)
    for index in range(period - 1, len(bars)):
        window = typical[index - period + 1:index + 1]
        mean = math.fsum(window) / period
        mad = math.fsum(abs(value - mean) for value in window) / period
        deviation = typical[index] - mean
        if _is_zero(mad, mean) or _is_zero(deviation, mean):
            out[index] = 0.0
        else:
            out[index] = deviation / (CCI_SCALE * mad)
    return out


def roc(closes: Sequence[float], period: int = 12) -> Series:
    """Değişim oranı, yüzde: (c / c[−n] − 1)·100. Referans kapanış 0 ise None."""
    _check_period(period)
    out: Series = [None] * len(closes)
    for index in range(period, len(closes)):
        base = closes[index - period]
        if base != 0.0:
            out[index] = (closes[index] / base - 1.0) * 100.0
    return out


# --- oynaklık ve trend gücü ---------------------------------------------------

def true_range(bars: Sequence[Bar]) -> Series:
    """Gerçek aralık. İlk mumda önceki kapanış yok, `high − low` alınır
    (StockCharts ve TradingView `ta.tr(true)` ile aynı)."""
    out: Series = []
    previous_close: float | None = None
    for bar in bars:
        if previous_close is None:
            out.append(bar.high - bar.low)
        else:
            out.append(max(bar.high - bar.low, abs(bar.high - previous_close),
                           abs(bar.low - previous_close)))
        previous_close = bar.close
    return out


def atr(bars: Sequence[Bar], period: int = 14) -> Series:
    """Wilder ATR: ilk `n` TR'nin ortalaması tohum, sonra Wilder yumuşatması.
    İlk değer `period − 1` indeksinde."""
    _check_period(period)
    ranges = [value for value in true_range(bars) if value is not None]
    return wilder_smooth(ranges, period)


def adx(bars: Sequence[Bar], period: int = 14) -> tuple[Series, Series, Series]:
    """(ADX, +DI, −DI), Wilder tanımıyla.

    +DM = yukarı hareket (h − h[−1]) eğer aşağı hareketten (l[−1] − l) büyük
    ve pozitifse, yoksa 0; −DM simetrik. TR, +DM ve −DM ayrı ayrı Wilder ile
    yumuşatılır. Wilder'ın özgün "toplam" biçimi yerine **ortalama** biçimi
    kullanılır: toplam biçimi her adımda tam olarak `n` katıdır ve DI bir oran
    olduğu için sonuç birebir aynıdır; ortalama biçimi TR ile aynı ölçekte
    kalıp ATR ile karşılaştırılabilir.

    DX = 100·|+DI − −DI| / (+DI + −DI); payda sıfırsa 0. ADX ilk `n` DX'in
    ortalamasıyla tohumlanır, sonra Wilder. Isınma: DI'lar `period`,
    ADX `2·period − 1` indeksinde başlar (14 için 28. mum).

    Düz seri: TR de DM'ler de 0 → DI'lar 0 → DX 0 → **ADX 0** (None değil;
    seri yeterince uzunsa "trend yok" ölçülmüş bir sonuçtur)."""
    _check_period(period)
    length = len(bars)
    empty: Series = [None] * length
    if length < 2:
        return empty, list(empty), list(empty)
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    ranges: list[float] = []
    for previous, current in zip(bars, bars[1:]):
        up_move = current.high - previous.high
        down_move = previous.low - current.low
        plus_dm.append(up_move if up_move > down_move and up_move > 0.0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0.0 else 0.0)
        ranges.append(max(current.high - current.low, abs(current.high - previous.close),
                          abs(current.low - previous.close)))
    smooth_tr = wilder_smooth(ranges, period)
    smooth_plus = wilder_smooth(plus_dm, period)
    smooth_minus = wilder_smooth(minus_dm, period)

    plus_di: Series = [None] * length
    minus_di: Series = [None] * length
    dx_values: list[float] = []
    for offset, (tr_value, plus, minus) in enumerate(zip(smooth_tr, smooth_plus, smooth_minus), start=1):
        if tr_value is None or plus is None or minus is None:
            continue
        p_di = 0.0 if tr_value == 0.0 else 100.0 * plus / tr_value
        m_di = 0.0 if tr_value == 0.0 else 100.0 * minus / tr_value
        plus_di[offset] = p_di
        minus_di[offset] = m_di
        total = p_di + m_di
        dx_values.append(0.0 if total == 0.0 else 100.0 * abs(p_di - m_di) / total)
    # DX dizisi `period` indeksinde başlar; seri ondan kısaysa boş kalır ve
    # ofset mum sayısına eşitlenir (sabit `period` ofseti hizayı bozardı).
    adx_line = _pad(wilder_smooth(dx_values, period), length - len(dx_values), length)
    return adx_line, plus_di, minus_di


def macd(closes: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[Series, Series, Series]:
    """(MACD, sinyal, histogram). MACD = EMA(fast) − EMA(slow), ikisi de SMA
    tohumlu; sinyal, ilk `signal` geçerli MACD değerinin SMA'sıyla tohumlanan
    EMA. Isınma: MACD `slow − 1`, sinyal ve histogram `slow + signal − 2`."""
    _check_period(fast, "fast")
    _check_period(slow, "slow")
    _check_period(signal, "signal")
    if fast >= slow:
        raise ValueError(f"fast ({fast}) slow'dan ({slow}) küçük olmalı")
    fast_line = ema(closes, fast)
    slow_line = ema(closes, slow)
    macd_line: Series = [
        None if f is None or s is None else f - s for f, s in zip(fast_line, slow_line)
    ]
    offset, tail = _valid_tail(macd_line)
    signal_line = _pad(ema(tail, signal), offset, len(closes))
    histogram: Series = [
        None if m is None or s is None else m - s for m, s in zip(macd_line, signal_line)
    ]
    return macd_line, signal_line, histogram


# --- hareketli ortalamalar ----------------------------------------------------

def moving_averages(closes: Sequence[float], periods: Sequence[int]) -> dict[int, tuple[float | None, float | None]]:
    """Her periyot için en son (SMA, EMA); yeterli veri yoksa None."""
    out: dict[int, tuple[float | None, float | None]] = {}
    for period in periods:
        if not closes:
            out[period] = (None, None)
            continue
        out[period] = (sma(closes, period)[-1], ema(closes, period)[-1])
    return out


def moving_average_table(bars: Sequence[Bar], params: IndicatorParams = IndicatorParams()) -> list[dict]:
    closes = [bar.close for bar in bars]
    last_close = closes[-1] if closes else None
    rows: list[dict] = []
    for period, (simple, exponential) in moving_averages(closes, params.ma_periods).items():
        above = None if simple is None or last_close is None else last_close > simple
        rows.append({"period": period, "sma": simple, "ema": exponential, "price_above_sma": above})
    return rows


# --- durum etiketleri ---------------------------------------------------------

def _band_state(value: float | None, overbought: float, oversold: float) -> IndicatorState | None:
    if value is None:
        return None
    if value >= overbought:
        return IndicatorState.OVERBOUGHT
    if value <= oversold:
        return IndicatorState.OVERSOLD
    return IndicatorState.NEUTRAL


def _sign_state(value: float | None, scale: float | None,
                positive: IndicatorState, negative: IndicatorState) -> IndicatorState | None:
    """`≥ 0` kuralı, göreli sıfır payıyla. Doğrusal bir yükselişte MACD ile
    sinyal aynı değere yakınsar ve histogram −1,8e−15 kalır; katı işaret
    kararı bunu "sinyalin altında" okuyordu. Ölçeğe göre sıfır sayılan değer
    `≥ 0` dalına düşer."""
    if value is None:
        return None
    if value >= 0.0 or _is_zero(value, scale or 0.0):
        return positive
    return negative


def _adx_state(value: float | None, params: IndicatorParams) -> IndicatorState | None:
    if value is None:
        return None
    if value >= params.adx_trending:
        return IndicatorState.TRENDING
    if value <= params.adx_weak:
        return IndicatorState.WEAK_TREND
    return IndicatorState.NEUTRAL


def _atr_baseline(atr_line: Sequence[float | None], window: int) -> float | None:
    """Son değer hariç, ondan önceki `window` ATR değerinin medyanı.

    Pencere **tam dolu** olmalı: yarım pencerede "normal oynaklık" farklı bir
    büyüklük olur ve etiket, tarih uzadıkça sessizce anlam değiştirirdi.
    Eksikse None; durum da None kalır."""
    history = [value for value in atr_line[:-1] if value is not None]
    if len(history) < window:
        return None
    return median(history[-window:])


def _atr_state(value: float | None, baseline: float | None, params: IndicatorParams) -> IndicatorState | None:
    if value is None or baseline is None or baseline <= 0.0:
        return None
    ratio = value / baseline
    if ratio >= params.atr_high_ratio:
        return IndicatorState.HIGH_VOLATILITY
    if ratio <= params.atr_low_ratio:
        return IndicatorState.LOW_VOLATILITY
    return IndicatorState.NORMAL_VOLATILITY


def _last(series: Sequence[float | None]) -> float | None:
    return series[-1] if series else None


def latest_indicators(bars: Sequence[Bar], params: IndicatorParams = IndicatorParams()) -> dict[str, IndicatorReading]:
    """Her göstergenin en son değeri, yardımcı büyüklükleri ve durum etiketi.
    Veri yetersizse okuma yine döner, `value` ve `state` None olur."""
    closes = [bar.close for bar in bars]

    rsi_value = _last(rsi(closes, params.rsi_period))
    k_line, d_line = stochastic(bars, params.stoch_k, params.stoch_d)
    k_value = _last(k_line)
    williams_value = _last(williams_r(bars, params.williams_period))
    cci_value = _last(cci(bars, params.cci_period))
    macd_line, signal_line, histogram = macd(closes, params.macd_fast, params.macd_slow, params.macd_signal)
    adx_line, plus_di, minus_di = adx(bars, params.adx_period)
    atr_line = atr(bars, params.atr_period)
    atr_value = _last(atr_line)
    atr_median = _atr_baseline(atr_line, params.atr_median_window)
    roc_value = _last(roc(closes, params.roc_period))

    return {
        "rsi": IndicatorReading(
            "rsi", rsi_value, {}, _band_state(rsi_value, params.rsi_overbought, params.rsi_oversold)),
        "stochastic": IndicatorReading(
            "stochastic", k_value, {"d": _last(d_line)},
            _band_state(k_value, params.stoch_overbought, params.stoch_oversold)),
        "williams": IndicatorReading(
            "williams", williams_value, {},
            _band_state(williams_value, params.williams_overbought, params.williams_oversold)),
        "cci": IndicatorReading(
            "cci", cci_value, {}, _band_state(cci_value, params.cci_band, -params.cci_band)),
        "macd": IndicatorReading(
            "macd", _last(macd_line), {"signal": _last(signal_line), "histogram": _last(histogram)},
            _sign_state(_last(histogram), _last(macd_line),
                        IndicatorState.ABOVE_SIGNAL, IndicatorState.BELOW_SIGNAL)),
        "adx": IndicatorReading(
            "adx", _last(adx_line), {"plus_di": _last(plus_di), "minus_di": _last(minus_di)},
            _adx_state(_last(adx_line), params)),
        "atr": IndicatorReading(
            "atr", atr_value, {"median": atr_median}, _atr_state(atr_value, atr_median, params)),
        "roc": IndicatorReading(
            "roc", roc_value, {}, _sign_state(roc_value, 1.0, IndicatorState.POSITIVE, IndicatorState.NEGATIVE)),
    }
