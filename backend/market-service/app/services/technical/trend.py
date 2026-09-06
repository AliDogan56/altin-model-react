"""Trend ve fiyat kanalı: seçilen dönemin genel yönü — noktaları birleştiren
çizgi değil, **regresyon**.

`frontend/src/domain/chart/trend.ts` + `features/trend/` (2026-09-06) buraya
birebir taşındı; arayüz artık hesap yapmaz, buradan çıkan bloğu çizer.
Matematik değişmedi, kanıtı `tests/fixtures/trend_expected_20260906.json`
(eski arayüzün ürettiği çıktı) ile parite testi.

Hesap fiyatın kendisi üzerinde değil **logaritması** üzerinde yapılır. Altın
gibi çok yıllık serilerde sabit yüzde büyüme fiyat ekseninde eğri bir çizgi
üretir; log uzayında düz olur. Böylece eğim "günde şu kadar dolar" değil
"dönem başına şu kadar yüzde" okunur ve serinin başı ile sonu eşit ağırlık taşır.

Ölçümle sabitlenmiş üç karar (arayüzdeki kayıtlar korunur):

* **Yön eşiği dönem boyu toplam değişimdir**, adım başına eğim değil. Eğim
  eşiği kova uzunluğuyla anlam değiştiriyordu: günlük mumda %0,1/gün yılda %28
  demek, 6 aylık kovada hiçbir şey. 90 günde −%6,37 olan gerçek seri "yatay"
  görünmüştü. Toplam değişim her kovada aynı şeyi söyler.
* **Sabit seride** log değerleri birebir aynı olsa da toplayıp bölmek ortalamayı
  bir ULP kaydırabiliyor; `syy` sıfır yerine ~1e-31 çıkıyor ve r² anlamsızlaşıyor
  (ölçüldü: yatay seride r² = 0). Log uzayında 1e-10'luk yayılım milyarda bir
  yüzde demektir; bu eşiğin altı düz kabul edilir (r² = 1, sigma 0).
* **Kanal betimleyicidir, sinyal değil.** Kanal dışına çıkmanın dönüş sinyali
  olduğu ölçülemedi (250 günlük regresyonda trendin 1σ altındayken sonraki 30
  günün ortalama getirisi koşulsuz ortalamanın *altında* çıktı, 33 bağımsız
  pencereyle gürültü). Bu yüzden blok konumu bildirir, yorum yapmaz.

Karta yazılan sayı **gerçekleşen** değişimdir (ilk ve son kapanış), trend
çizgisinin uçları değil: 60 aylık seride ham %148 iken trend uçları %203 idi ve
okuyucu bunu fiyat değişimi sanardı. İkisi de döner, ayrı adlarla.

Mum gövdesi "açılış → kapanış" değil **önceki kapanış → kapanış**: kaynak
açılış vermiyor (`d, c, h, l`). Fitil gerçek gün içi aralık; kapanış ya da
önceki kapanış aralığın dışındaysa fitil onları da kapsayacak şekilde uzatılır
(gövde ile fitil çelişmesin). Dilimin ilk mumu için önceki kapanış dilimden
**önceki** kovadan alınır ki ilk gövde de gerçek olsun.

Bütün fonksiyonlar saf ve belirlenimcidir; numpy yok, tek geçiş O(n).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.services.technical.candles import Candle, Timeframe, aggregate, period_end

# Durum ve etiket sabitleri; metin olarak taşınır, JSON'a doğrudan girer.
STATUS_OK = "OK"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

DIRECTION_UP = "UP"
DIRECTION_DOWN = "DOWN"
DIRECTION_FLAT = "FLAT"

CHANNEL_BELOW_2 = "BELOW_2SIGMA"
CHANNEL_BELOW_1 = "BELOW_1SIGMA"
CHANNEL_NEAR = "NEAR_TREND"
CHANNEL_ABOVE_1 = "ABOVE_1SIGMA"
CHANNEL_ABOVE_2 = "ABOVE_2SIGMA"

FIT_GOOD = "GOOD"
FIT_MODERATE = "MODERATE"
FIT_WEAK = "WEAK"


@dataclass(frozen=True)
class TrendParams:
    """Trend bloğunun ayarları.

    `flat_limit`: yönün "yatay" sayıldığı eşik — dönem boyu **toplam** değişim
    (0,01 = %1). `flat_syy_per_n`: log uzayında nokta başına yayılım bu değerin
    altındaysa seri sabit kabul edilir (kayan nokta gürültüsü, yukarıda).
    `channel_z`: kanal bantlarının sigma katsayıları (±1σ, ±2σ) ve konum
    etiketlerinin eşikleri. `fit_r2`: uyum etiketinin eşikleri (iyi, orta).
    `ranges`: (kimlik, çerçeve, nokta sayısı) — kaynak beş yıllık günlük seri
    olduğu için üst aralıklarda nokta sayısı doğal olarak azdır (6 aylıkta
    ~10); bu eksiklik değil, yeter ki nokta sayısı bildirilsin. `min_points`:
    bunun altında uydurma yapılmaz.
    """

    flat_limit: float = 0.01
    flat_syy_per_n: float = 1e-20
    channel_z: tuple[float, float] = (1.0, 2.0)
    fit_r2: tuple[float, float] = (0.75, 0.40)
    ranges: tuple[tuple[str, Timeframe, int], ...] = (
        ("gunluk", Timeframe.DAILY, 90),
        ("haftalik", Timeframe.WEEKLY, 104),
        ("aylik", Timeframe.MONTHLY, 60),
        ("ceyreklik", Timeframe.QUARTERLY, 24),
        ("yarim", Timeframe.SEMIANNUAL, 12),
    )
    min_points: int = 3


@dataclass(frozen=True)
class TrendFit:
    """Log fiyat üzerinde en küçük kareler doğrusu.

    `slope` log-fiyat / adım; `slope_pct` aynı şeyin oransal karşılığı
    (expm1, 0,004 = dönem başına %0,4). `first`/`last` doğrunun ilk ve son
    noktadaki fiyat karşılığı; `change_pct` bunların oranı eksi bir — yön
    kararı buradan verilir. `sigma` artıkların standart sapması, **log
    uzayında** yani oransal (0,086 = "trend etrafında tipik sapma %8,6");
    kanal genişliği budur. `last_z` son gözlemin trende göre konumu, sigma
    cinsinden. `n` uydurmaya giren geçerli nokta sayısı.
    """

    n: int
    intercept: float
    slope: float
    slope_pct: float
    first: float
    last: float
    r2: float
    change_pct: float
    direction: str
    sigma: float
    last_z: float


@dataclass(frozen=True)
class TrendRow:
    """Grafiğin bir noktası: kova mumu + o noktadaki trend ve kanal.

    `pc` önceki kovanın kapanışı (gövdenin diğer ucu), serinin en başında yok.
    `wh`/`wl` fitil: aralık, kapanış ve önceki kapanışı kapsayacak şekilde
    genişletilmiş. `b1`/`b2` (alt, üst) bant; `complete` kovanın takvimce
    bittiği (oluşmakta olan son kova yanlış okunmasın).
    """

    d: date
    h: float
    l: float
    c: float
    pc: float | None
    wh: float
    wl: float
    fit: float
    b1: tuple[float, float]
    b2: tuple[float, float]
    complete: bool


@dataclass(frozen=True)
class TrendRange:
    """Bir aralığın tam bloğu. `candles` yalnız günlükte doğru (diğerleri
    çizgi çizer). `INSUFFICIENT_DATA`'da uydurma yapılmaz; satırların fit ve
    bant alanları uydurmasız doldurulamayacağı için `rows` boş kalır."""

    id: str
    timeframe: Timeframe
    bars: int
    candles: bool
    status: str
    last_bucket_forming: bool
    fit: TrendFit | None
    realized_pct: float | None
    channel_state: str | None
    fit_state: str | None
    rows: tuple[TrendRow, ...]


# --- regresyon ----------------------------------------------------------------

def _direction(change_pct: float, flat_limit: float) -> str:
    if change_pct > flat_limit:
        return DIRECTION_UP
    if change_pct < -flat_limit:
        return DIRECTION_DOWN
    return DIRECTION_FLAT


def trend_fit(values: Sequence[float], params: TrendParams = TrendParams()) -> TrendFit:
    """Log fiyat üzerinde OLS. `values` sıralı kapanışlar; x ekseni dizin.

    Sonlu ve pozitif olmayan değerler atlanır ama dizinleri korunur (x ekseni
    kaymaz). En az iki geçerli nokta gerekir; yoksa ValueError — arayüzdeki
    `null` karşılığı. Toplamlar tek geçişte ve kaynakla aynı sırada alınır ki
    çıktı bit düzeyinde karşılaştırılabilsin.
    """
    xs: list[float] = []
    ys: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number > 0:
            xs.append(float(index))
            ys.append(math.log(number))
    n = len(ys)
    if n < 2:
        raise ValueError(f"trend için en az iki geçerli nokta gerekir, {n} var")

    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    sxy = sxx = syy = 0.0
    for x, y in zip(xs, ys):
        dx, dy = x - x_mean, y - y_mean
        sxy += dx * dy
        sxx += dx * dx
        syy += dy * dy
    if sxx == 0:
        raise ValueError("trend için x ekseninde yayılım yok")

    # Sabit seri: kayan nokta gürültüsü yüzünden syy ~1e-31 çıkabiliyor; log
    # uzayında n·1e-20 altı düz kabul edilir (r² = 1, kanal sıfır).
    if syy <= n * params.flat_syy_per_n:
        constant = math.exp(y_mean)
        return TrendFit(n=n, intercept=y_mean, slope=0.0, slope_pct=0.0,
                        first=constant, last=constant, r2=1.0, change_pct=0.0,
                        direction=DIRECTION_FLAT, sigma=0.0, last_z=0.0)

    slope = sxy / sxx                       # log-fiyat / adım
    intercept = y_mean - slope * x_mean
    r2 = 1.0 if syy == 0 else min(1.0, max(0.0, (sxy * sxy) / (sxx * syy)))

    # Kanal: artıkların standart sapması, ddof = 0 (popülasyon). Log uzayında
    # hesaplandığı için bant fiyat ekseninde çarpımsal açılır — %8'lik sapma
    # yüksek fiyatta daha çok dolar eder ve bant öyle görünmelidir.
    squares = 0.0
    for x, y in zip(xs, ys):
        residual = y - (intercept + slope * x)
        squares += residual * residual
    sigma = math.sqrt(squares / n)
    last_residual = ys[-1] - (intercept + slope * xs[-1])
    last_z = last_residual / sigma if sigma > 0 else 0.0

    # Uçlar: ilk nokta ve girdinin SON dizini (geçerli nokta sayısı değil) —
    # kaynakla aynı; atlanan uç değer olsa da doğru serinin sonuna uzatılır.
    first = math.exp(intercept)
    last = math.exp(intercept + slope * (len(values) - 1))
    change_pct = last / first - 1 if first > 0 else 0.0
    return TrendFit(n=n, intercept=intercept, slope=slope, slope_pct=math.expm1(slope),
                    first=first, last=last, r2=r2, change_pct=change_pct,
                    direction=_direction(change_pct, params.flat_limit),
                    sigma=sigma, last_z=last_z)


def fit_at(fit: TrendFit, i: int) -> float:
    """i. noktadaki uydurulmuş fiyat — veri değil, doğru."""
    return math.exp(fit.intercept + fit.slope * i)


def band(fit: TrendFit, i: int, k: float) -> tuple[float, float]:
    """i. noktada trendin k sigma altı ve üstü, (alt, üst). k = 0 doğrunun
    kendisi; sigma sıfırsa iki uç da tam olarak `fit_at(i)`."""
    center = fit_at(fit, i)
    return center * math.exp(-k * fit.sigma), center * math.exp(k * fit.sigma)


# --- etiketler ------------------------------------------------------------------

def channel_state(last_z: float, params: TrendParams = TrendParams()) -> str:
    """Son gözlemin kanaldaki yeri. Eşikler katı (tam 1σ "yakın" sayılır);
    arayüzün `kanalMetni` kuralıyla aynı."""
    z1, z2 = params.channel_z
    if last_z > z2:
        return CHANNEL_ABOVE_2
    if last_z > z1:
        return CHANNEL_ABOVE_1
    if last_z < -z2:
        return CHANNEL_BELOW_2
    if last_z < -z1:
        return CHANNEL_BELOW_1
    return CHANNEL_NEAR


def fit_state(r2: float, params: TrendParams = TrendParams()) -> str:
    """Uyum iyiliği sade dille: r² tek başına okura bir şey söylemiyor."""
    good, moderate = params.fit_r2
    if r2 >= good:
        return FIT_GOOD
    if r2 >= moderate:
        return FIT_MODERATE
    return FIT_WEAK


# --- blok ---------------------------------------------------------------------------

def _empty_range(range_id: str, timeframe: Timeframe, bars: int, forming: bool) -> TrendRange:
    return TrendRange(id=range_id, timeframe=timeframe, bars=bars,
                      candles=timeframe is Timeframe.DAILY, status=STATUS_INSUFFICIENT_DATA,
                      last_bucket_forming=forming, fit=None, realized_pct=None,
                      channel_state=None, fit_state=None, rows=())


def _build_range(range_id: str, timeframe: Timeframe, bars: int, daily: Sequence[Candle],
                 today: date, params: TrendParams) -> TrendRange:
    series = aggregate(daily, timeframe)
    # Son N kova; ilk gövde için bir kova daha geriye bakılır ama o kova çizilmez.
    rows_in = series[-bars:] if bars > 0 else []
    previous = series[-bars - 1] if 0 < bars < len(series) else None
    forming = bool(rows_in) and period_end(rows_in[-1].date, timeframe) >= today

    if len(rows_in) < params.min_points:
        return _empty_range(range_id, timeframe, bars, forming)
    try:
        fit = trend_fit([candle.close for candle in rows_in], params)
    except ValueError:
        return _empty_range(range_id, timeframe, bars, forming)

    z1, z2 = params.channel_z
    rows: list[TrendRow] = []
    prev_close: float | None = previous.close if previous is not None else None
    for i, candle in enumerate(rows_in):
        # Fitil, gövdenin iki ucunu da kapsar: kaynak kapanışı nadiren aralığın
        # dışında verebiliyor, gövde ile fitil çelişmesin.
        body = (candle.close,) if prev_close is None else (candle.close, prev_close)
        rows.append(TrendRow(
            d=candle.date, h=candle.high, l=candle.low, c=candle.close, pc=prev_close,
            wh=max(candle.high, *body), wl=min(candle.low, *body),
            fit=fit_at(fit, i), b1=band(fit, i, z1), b2=band(fit, i, z2),
            complete=period_end(candle.date, timeframe) < today))
        prev_close = candle.close

    first_close, last_close = rows_in[0].close, rows_in[-1].close
    realized = last_close / first_close - 1 if len(rows_in) > 1 and first_close > 0 else None
    return TrendRange(id=range_id, timeframe=timeframe, bars=bars,
                      candles=timeframe is Timeframe.DAILY, status=STATUS_OK,
                      last_bucket_forming=forming, fit=fit, realized_pct=realized,
                      channel_state=channel_state(fit.last_z, params),
                      fit_state=fit_state(fit.r2, params), rows=tuple(rows))


def trend_block(candles: Sequence[Candle], today: date,
                params: TrendParams = TrendParams()) -> dict[str, TrendRange]:
    """Beş aralığın tamamı, `params.ranges` sırasıyla ve kimliğe göre.

    `candles` normalize edilmiş günlük mumlar (`candles.normalize_daily`);
    çağıran oluşmakta olan günü zaten çıkarmış olmalı, yine de `today` ile son
    kovanın oluşup oluşmadığı bildirilir. Sıralı girdi Timsort'ta O(n)
    doğrulanır; sırasız gelirse de sonuç aynıdır.
    """
    daily = sorted(candles, key=lambda candle: candle.date)
    return {range_id: _build_range(range_id, timeframe, bars, daily, today, params)
            for range_id, timeframe, bars in params.ranges}
