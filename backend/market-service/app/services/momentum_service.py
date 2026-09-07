"""Gün içi momentum ve destek/direnç kırılım gücü.

Amaç fiyatın yükselip düştüğünü söylemek değil: **mevcut hareketin ilk destek
veya direnci kırabilecek güçte olup olmadığını** ölçmek.

Sabit eşik yok. Bütün büyüklükler o anın gün içi oynaklığına göre normalize
edilir, yani aynı 10 dolarlık hareket sakin bir seansta güçlü, çalkantılı bir
seansta zayıf okunur:

* Her gösterge işaretli bir **z-benzeri** sayıya çevrilir (birim: o seansın
  mum getirisi standart sapması).
* Güç, sinyalin oynaklık birimindeki **büyüklüğü**dür; göstergelerin ne kadar
  hemfikir olduğuyla ölçeklenip lojistikle 0-100'e sıkıştırılır. Böylece "70
  üzeri güçlü" gibi bir eşik gerekmez.
  Gücü t istatistiğine bağlamak **denendi ve yanlış çıktı**: bileşenler birlikte
  sıfıra çöktüğünde t yüksek kalıyor ve çalkantılı seans sakin seanstan güçlü
  okunuyordu (ölçüldü: 72 > 63; düzeltmeden sonra 3 < 51).
* Yön ayrı bir sorudur ve t istatistiğiyle karara bağlanır: ortalama sinyal bir
  standart hatadan küçükse **NEUTRAL** — büyüklük eşiğiyle değil, istatistiksel
  ayırt edilebilirlikle.
* Kırılım gücü iki şeyi birden ister: seviyeye **ulaşmak** (beklenen hareket ÷
  uzaklık, 1'de doyurulur) ve onu **kırmaya yetecek momentum**. İkisinin
  geometrik ortalaması 0-1 arası bir skor verir; etiketler bu skorun
  üçte birlik dilimlerinden çıkar.
  Yalnız ulaşma oranına bakmak yanlıştı: fiyat seviyeye 0,2 sigma yakınken oran
  88'e fırlıyor ve her şey "STRONG" oluyordu (gerçek veride ölçüldü). Seviyenin
  dibinde olmak onu kırmakla aynı şey değildir.

Hacim varsa teyit bileşeni olarak girer, yoksa hesap hacimsiz kurulur ve bu
yanıtta bildirilir.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

# Göstergelerin okuduğu pencere: 5 dakikalık mumda 12 mum = 1 saat. Kısa vadeli
# momentum için anlamlı, tek bir sıçramaya da teslim olmayacak kadar uzun.
WINDOW = 12
RSI_PERIOD = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
# Anlamlı bir oynaklık tahmini için gereken en az mum sayısı.
MIN_BARS = MACD_SLOW + MACD_SIGNAL + WINDOW
EPS = 1e-12

# Bileşen ağırlıkları. Bunlar eşik değil, **editoryal bir tercih**: hız asıl
# momentum ölçüsüdür (fiyat gerçekten hareket ediyor mu), diğerleri teyit eder.
# Eşit ağırlık denendi ve tek düze bir trendi olduğundan zayıf gösteriyordu:
# ivme ve MACD histogramı sabit hızlı bir trendde matematiksel olarak sıfıra
# yakınsar, ortalamaya girince gücü aşağı çekiyorlardı.
WEIGHTS = {"velocity": 0.25, "drift": 0.20, "acceleration": 0.20,
           "rsi": 0.10, "macd": 0.10, "volume": 0.15}

# --- seviye çerçeveleri -------------------------------------------------------
# Tek başına günlük pivot yetmiyordu. İki ayrı kusur ölçüldü (2026-09-01):
#   1) Merdiven 5 dakikalık akışın **kırpılmış** önceki seansından türetiliyordu:
#      aralık 32,14 $ çıkıyordu, günlük mumun gerçek aralığı 56,0 $. Seviyeler
#      olduğu gibi yanlıştı (S2 4413,47 yerine 4380,30).
#   2) Fiyat merdivenin ucuna gelince "kırılacak seviye yok" deniyordu. Oysa bir
#      sonraki anlamlı seviye vardı: haftalık S2 4314,50 ve 14 Ağustos salınım
#      dibi 4315,00 — iki ayrı çerçeve aynı yeri gösteriyor.
# Çözüm: pivotlar **günlük mumdan** hesaplanır ve günlük + haftalık + salınım
# seviyeleri tek merdivende birleştirilir.
SWING_LOOKBACK = 40   # salınımın arandığı günlük mum sayısı
SWING_WING = 2        # fraktal kanadı: tepe/dip iki komşusunu da aşmalı
# Kümeleme toleransı da sabit değil: iki seviye ~4 mumluk gürültü içindeyse
# fiyat açısından ayırt edilemez, tek seviye sayılır.
CLUSTER_BARS = 4


@dataclass(frozen=True)
class Bar:
    t: datetime
    o: float
    h: float
    l: float
    c: float
    v: int


def parse_bars(rows: Sequence[dict]) -> list[Bar]:
    bars = []
    for row in rows:
        try:
            bars.append(Bar(datetime.fromisoformat(row["t"]), float(row["o"]), float(row["h"]),
                            float(row["l"]), float(row["c"]), int(row.get("v") or 0)))
        except (KeyError, TypeError, ValueError):
            continue
    bars.sort(key=lambda bar: bar.t)
    return bars


# --- yardımcılar --------------------------------------------------------------

def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    average = _mean(values)
    return math.sqrt(sum((value - average) ** 2 for value in values) / (len(values) - 1))


def _logistic(x: float) -> float:
    # Taşmayı önlemek için sınırlanır; ±40 zaten 0/1'e doymuş demektir.
    return 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, x))))


def _ema(values: Sequence[float], period: int) -> list[float]:
    if not values:
        return []
    k = 2.0 / (period + 1)
    out = [values[0]]
    for value in values[1:]:
        out.append(value * k + out[-1] * (1 - k))
    return out


def log_returns(closes: Sequence[float]) -> list[float]:
    return [math.log(b / a) for a, b in zip(closes, closes[1:]) if a > 0 and b > 0]


def rsi(closes: Sequence[float], period: int = RSI_PERIOD) -> float | None:
    """Wilder RSI; yeterli mum yoksa None."""
    if len(closes) <= period:
        return None
    gains, losses = [], []
    for previous, current in zip(closes, closes[1:]):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain, avg_loss = _mean(gains[:period]), _mean(losses[:period])
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss <= EPS:
        return 100.0 if avg_gain > EPS else 50.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def macd_histogram(closes: Sequence[float]) -> float | None:
    """MACD histogramının son değeri (fiyat birimi)."""
    if len(closes) < MACD_SLOW + MACD_SIGNAL:
        return None
    fast, slow = _ema(closes, MACD_FAST), _ema(closes, MACD_SLOW)
    line = [f - s for f, s in zip(fast, slow)]
    signal = _ema(line, MACD_SIGNAL)
    return line[-1] - signal[-1]


# --- destek / direnç ----------------------------------------------------------

def daily_pivots(high: float, low: float, close: float) -> dict[str, float]:
    """Bir önceki tamamlanmış seanstan klasik pivot merdiveni.

    Gün içi referans olarak günlük pivot kullanılır; panelin başka yerindeki
    haftalık/aylık pivotlarla aynı formül, yalnız dönem farklı.
    """
    pivot = (high + low + close) / 3
    span = high - low
    return {
        "R3": high + 2 * (pivot - low), "R2": pivot + span, "R1": 2 * pivot - low,
        "P": pivot,
        "S1": 2 * pivot - high, "S2": pivot - span, "S3": low - 2 * (high - pivot),
    }


def _complete_days(daily: Sequence[dict], today) -> list[dict]:
    """Bugünün **devam eden** mumu merdivene girmez; kapanışı henüz yok."""
    out = []
    for row in daily:
        try:
            day = date.fromisoformat(str(row["d"]))
        except (KeyError, ValueError):
            continue
        if day < today and all(row.get(k) is not None for k in ("h", "l", "c")):
            out.append({"day": day, "h": float(row["h"]),
                        "l": float(row["l"]), "c": float(row["c"])})
    out.sort(key=lambda r: r["day"])
    return out


def last_complete_week(days: Sequence[dict], today) -> list[dict]:
    """Son tamamlanmış ISO hafta.

    Hafta cumartesi girince tamamlanmış sayılır — panelin pivot kartıyla aynı
    kural. Koşulsuzca "sondan bir önceki hafta" almak seviyeleri bir hafta bayat
    bırakıyordu.
    """
    if not days:
        return []
    current = today.isocalendar()[:2]
    groups: dict[tuple[int, int], list[dict]] = {}
    for row in days:
        groups.setdefault(row["day"].isocalendar()[:2], []).append(row)
    keys = sorted(groups)
    if today.isoweekday() < 6:
        keys = [k for k in keys if k != current]
    return groups[keys[-1]] if keys else []


def swing_levels(days: Sequence[dict]) -> list[tuple[str, float]]:
    """Fiyatın fiilen döndüğü noktalar: iki komşusunu da aşan tepe ve dipler."""
    window = list(days)[-SWING_LOOKBACK:]
    out: list[tuple[str, float]] = []
    for i in range(SWING_WING, len(window) - SWING_WING):
        chunk = window[i - SWING_WING:i + SWING_WING + 1]
        row = window[i]
        stamp = row["day"].strftime("%d.%m")
        if row["l"] == min(c["l"] for c in chunk):
            out.append((f"{stamp} dibi", row["l"]))
        if row["h"] == max(c["h"] for c in chunk):
            out.append((f"{stamp} zirvesi", row["h"]))
    return out


def cluster_levels(raw: Sequence[tuple[int, str, float]], tolerance: float
                   ) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Birbirine tolerans kadar yakın seviyeleri tek seviyede toplar.

    Aynı yeri gösteren iki çerçeve ayrı seviye gibi listelenirse merdiven
    şişer ve "iki kaynak da burayı işaret ediyor" bilgisi kaybolur.
    """
    ordered = sorted(raw, key=lambda item: item[2])
    clusters: list[list[tuple[int, str, float]]] = []
    for item in ordered:
        if clusters and item[2] - clusters[-1][-1][2] <= tolerance:
            clusters[-1].append(item)
        else:
            clusters.append([item])

    levels: dict[str, float] = {}
    sources: dict[str, list[str]] = {}
    for group in clusters:
        # Etiket en yüksek öncelikli çerçeveden gelir (günlük > haftalık > salınım).
        primary = min(group, key=lambda item: item[0])
        label = primary[1]
        while label in levels:
            label += "'"
        levels[label] = sum(item[2] for item in group) / len(group)
        sources[label] = [item[1] for item in sorted(group, key=lambda i: i[0])]
    return levels, sources


def build_levels(daily: Sequence[dict], today, tolerance: float
                 ) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Günlük + haftalık pivotlar ve salınım noktalarından tek merdiven."""
    days = _complete_days(daily, today)
    if not days:
        return {}, {}

    raw: list[tuple[int, str, float]] = []
    last = days[-1]
    for name, value in daily_pivots(last["h"], last["l"], last["c"]).items():
        raw.append((0, name, value))

    week = last_complete_week(days, today)
    if week:
        high = max(r["h"] for r in week); low = min(r["l"] for r in week)
        for name, value in daily_pivots(high, low, week[-1]["c"]).items():
            raw.append((1, f"Haftalık {name}", value))

    for name, value in swing_levels(days):
        raw.append((2, name, value))

    return cluster_levels(raw, tolerance)


def nearest_levels(levels: dict[str, float], price: float, margin: float = 0.0
                   ) -> tuple[tuple[str, float] | None, tuple[str, float] | None]:
    """(fiyatın hemen altındaki destek, hemen üstündeki direnç).

    `margin` kadar yakın seviyeler atlanır: fiyat bir seviyenin üstünde
    duruyorsa o seviye "kırılacak" değil **zaten test ediliyor** demektir ve
    hedef olarak göstermek kullanıcıyı yanıltır (kullanıcı bildirdi: gösterilen
    seviye çoktan kırılmıştı). Marj gürültü genişliğidir, sabit bir sayı değil.
    """
    below = [(name, value) for name, value in levels.items() if value < price - margin]
    above = [(name, value) for name, value in levels.items() if value > price + margin]
    support = max(below, key=lambda item: item[1]) if below else None
    resistance = min(above, key=lambda item: item[1]) if above else None
    return support, resistance


# --- momentum -----------------------------------------------------------------

def _components(bars: Sequence[Bar], sigma: float) -> dict[str, float]:
    """Her gösterge, o seansın oynaklığı biriminde işaretli bir sayıya çevrilir."""
    closes = [bar.c for bar in bars]
    window = min(WINDOW, len(closes) - 1)

    # Hız: son pencerede biriken getiri, aynı pencerede rastgele yürüyüşten
    # beklenen dağılıma (sigma*sqrt(n)) bölünür.
    drift = math.log(closes[-1] / closes[-1 - window]) if closes[-1 - window] > 0 else 0.0
    velocity = drift / (sigma * math.sqrt(window) + EPS)

    # İvme: bu pencerenin hızı ile bir önceki pencerenin hızı arasındaki fark.
    previous = 0.0
    if len(closes) > 2 * window:
        earlier = math.log(closes[-1 - window] / closes[-1 - 2 * window])
        previous = earlier / (sigma * math.sqrt(window) + EPS)
    acceleration = velocity - previous

    strength_rsi = rsi(closes)
    rsi_z = 0.0 if strength_rsi is None else (strength_rsi - 50.0) / 50.0 * 2.0

    histogram = macd_histogram(closes)
    macd_z = 0.0 if histogram is None else histogram / (closes[-1] * sigma + EPS)

    return {"velocity": velocity, "acceleration": acceleration,
            "rsi": rsi_z, "macd": macd_z, "previous_velocity": previous}


def session_drift(closes: Sequence[float], sigma: float) -> float | None:
    """Seans açılışından bu yana biriken sürüklenme, sigma biriminde.

    Hız yalnız **son bir saate** bakıyordu ve gün boyu süren yavaş bir trendi
    hiç görmüyordu. Ölçüldü (2026-09-01): son 1 saat z = -0,83 iken seansın
    tamamı -96 $ ve z = -1,65. Sürüklenme n ile birikirken gürültü yalnız √n
    ile büyüdüğü için uzun pencere aynı eşikte **daha güçlü** bir testtir;
    duyarlılık eşiği gevşeterek değil, tahmin ediciyi güçlendirerek artar.

    Seans başında birkaç mumdan hesaplanan oran anlamsız olacağı için en az
    bir pencere dolusu mum istenir; yoksa bileşen hiç katılmaz ve ağırlığı
    kalanlara dağıtılır.
    """
    if len(closes) <= WINDOW or sigma <= EPS:
        return None
    span = len(closes) - 1
    return math.log(closes[-1] / closes[0]) / (sigma * math.sqrt(span))


def _volume_confirmation(bars: Sequence[Bar]) -> float | None:
    """Son pencere hacminin seans medyanına oranı, log ölçekte.

    Hacim yoksa None döner ve hesaba hiç katılmaz — sıfır saymak "hacim
    ortalamada" demek olurdu, bu yanlış bir bilgi olurdu.
    """
    volumes = [bar.v for bar in bars if bar.v > 0]
    if len(volumes) < WINDOW * 2:
        return None
    recent = _mean(volumes[-WINDOW:])
    ordered = sorted(volumes)
    median = ordered[len(ordered) // 2]
    if median <= 0 or recent <= 0:
        return None
    return math.log(recent / median)


def momentum(rows: Sequence[dict], *, daily: Sequence[dict] | None = None,
             session_bars: int | None = None) -> dict:
    """Gün içi momentum ve kırılım gücü raporu.

    `daily` günlük OHLC serisidir ve seviye merdiveni ondan kurulur. Verilmezse
    merdiven gün içi akıştan türetilir; o yol aralığı olduğundan dar ölçtüğü
    için yalnız yedektir.
    """
    bars = parse_bars(rows)
    if len(bars) < MIN_BARS:
        raise ValueError(f"Momentum için en az {MIN_BARS} gün içi mum gerekli; {len(bars)} geldi")

    today = bars[-1].t.date()
    session = [bar for bar in bars if bar.t.date() == today]
    history = [bar for bar in bars if bar.t.date() != today]

    # Oynaklık referansı: bugünün mumları yeterliyse bugünden, değilse tüm
    # pencereden. Seans başında bugün birkaç mumdan ibaret olur ve ondan
    # hesaplanan sigma anlamsız çıkar.
    basis = session if len(session) >= WINDOW * 2 else bars
    sigma = _stdev(log_returns([bar.c for bar in basis]))
    if sigma <= EPS:
        raise ValueError("Gün içi oynaklık sıfır; momentum hesaplanamaz")

    parts = _components(bars, sigma)
    drift_z = session_drift([bar.c for bar in basis], sigma)
    if drift_z is not None:
        parts["drift"] = drift_z
    volume_z = _volume_confirmation(session if len(session) >= WINDOW * 2 else bars)

    # Hacim yönsüzdür: hareketi teyit eder, yönü belirlemez. Bu yüzden hızın
    # işaretiyle çarpılarak diğer bileşenlerle aynı eksene taşınır.
    signals = {"velocity": parts["velocity"], "acceleration": parts["acceleration"],
               "rsi": parts["rsi"], "macd": parts["macd"]}
    if drift_z is not None:
        signals["drift"] = drift_z
    if volume_z is not None:
        # Hacim yönsüzdür: hareketi teyit eder, yönü belirlemez.
        signals["volume"] = math.copysign(abs(volume_z), parts["velocity"] or 1.0)

    # Hacim yoksa ağırlıklar kalan bileşenlere yeniden dağıtılır.
    total_weight = sum(WEIGHTS[name] for name in signals)
    average = sum(signals[name] * WEIGHTS[name] for name in signals) / total_weight
    dispersion = math.sqrt(sum(WEIGHTS[name] * (signals[name] - average) ** 2
                               for name in signals) / total_weight)
    # t yalnız **yön ayırt edilebilir mi** sorusunu cevaplar.
    t_stat = average / (dispersion / math.sqrt(len(signals)) + EPS)

    # Güç ayrı bir sorudur: sinyalin oynaklık birimindeki **büyüklüğü**, ne
    # kadar hemfikir olunduğuyla ölçeklenir. Gücü t'ye bağlamak yanlıştı;
    # bileşenler birlikte sıfıra çöktüğünde t yüksek kalıyor ve çalkantılı
    # seans sakin seanstan güçlü okunuyordu.
    consistency = abs(average) / (abs(average) + dispersion + EPS)
    strength = round(100 * (2 * _logistic(abs(average) * (0.5 + consistency)) - 1))

    # Yön iki koşul birden ister:
    #   1) bileşik sinyal gürültüden ayırt edilebilsin (|t| >= 1), ve
    #   2) fiyatın kendisi rastgele yürüyüşten sapmış olsun (|hız| >= 1 sigma).
    # Tek başına t yetmiyordu: sürüklenmesiz bir seride bileşenler küçük ama
    # tutarlı olduğunda t 1'i aşıp sahte yön üretiyordu (ölçüldü: hız 0,00
    # iken "UP").
    # Fiyatın kendisi rastgele yürüyüşten sapmış olmalı; bu iki zaman ölçeğinden
    # **hangisi baskınsa** ondan sorulur: son bir saatlik itiş ya da seansın
    # tamamındaki sürüklenme. Tek bir pencereye bağlı kalmak, gün boyu süren
    # yavaş trendleri görünmez kılıyordu.
    move_z = max(abs(parts["velocity"]), abs(drift_z or 0.0))
    distinguishable = abs(t_stat) >= 1.0 and move_z >= 1.0
    direction = ("UP" if average > 0 else "DOWN") if distinguishable else "NEUTRAL"

    # Momentum güçleniyor mu: hız büyüklüğündeki değişim, gürültüye kıyasla.
    delta = abs(parts["velocity"]) - abs(parts["previous_velocity"])
    trend = "STABLE"
    if abs(delta) >= 1.0 / math.sqrt(WINDOW):
        trend = "STRENGTHENING" if delta > 0 else "WEAKENING"

    price = bars[-1].c
    # Kümeleme toleransı da seansın kendi gürültüsünden gelir; sabit dolar yok.
    tolerance = price * sigma * math.sqrt(CLUSTER_BARS)
    levels, sources = build_levels(daily or [], today, tolerance)
    if not levels and history:
        # Günlük seri gelmediyse gün içi akıştan türet: aralığı dar ölçer ama
        # bölümü tamamen susturmaktan iyidir.
        previous_day = max(bar.t.date() for bar in history)
        prior = [bar for bar in history if bar.t.date() == previous_day]
        levels = daily_pivots(max(b.h for b in prior), min(b.l for b in prior), prior[-1].c)
        sources = {name: [name] for name in levels}
    support, resistance = (nearest_levels(levels, price, tolerance) if levels
                           else (None, None))
    # Fiyatın fiilen üzerinde durduğu seviye: hedef değil, ayrı bir bilgi.
    touching = min(((name, value) for name, value in levels.items()
                    if abs(value - price) <= tolerance),
                   key=lambda item: abs(item[1] - price), default=None)
    # Güçlü bir trend günü merdiveni tamamen aşabilir. Sessizce boş dönmek
    # kullanıcıya hiçbir şey söylemez; hangi uçtan çıkıldığını bildiriyoruz.
    outside = None
    if levels:
        if resistance is None:
            outside = "above"
        elif support is None:
            outside = "below"

    # Seans sonuna kalan mum: önceki seansların uzunluğundan türetilir, sabit
    # bir sayı varsayılmaz (altın seansı kaynağa göre değişiyor).
    if session_bars is None:
        lengths = [sum(1 for bar in history if bar.t.date() == day)
                   for day in {bar.t.date() for bar in history}]
        session_bars = max(lengths) if lengths else len(session)
    remaining = max(1, session_bars - len(session))

    # Beklenen hareket: rastgele yürüyüş taban + momentumun yönlü katkısı.
    boost = 1.0 + max(0.0, abs(t_stat)) / (1.0 + abs(t_stat))
    expected_move = price * sigma * math.sqrt(remaining) * boost

    target = None
    if direction == "UP" and resistance:
        target = ("resistance", resistance)
    elif direction == "DOWN" and support:
        target = ("support", support)
    elif support and resistance:                       # NEUTRAL: yakın olan hedef
        target = min((("support", support), ("resistance", resistance)),
                     key=lambda item: abs(item[1][1] - price))

    breakout = None
    if target:
        name, (level_name, level_value) = target[0], target[1]
        distance = abs(level_value - price)
        reach = expected_move / (distance + EPS)
        # Ulaşma 1'de doyurulur: seviyenin dibindeyken oranın 88'e fırlaması
        # ayırt edici bir bilgi taşımıyor. Kırmak için ayrıca momentum gerekir.
        score = math.sqrt(min(1.0, reach) * (strength / 100))
        label = "STRONG" if score >= 2 / 3 else ("MEDIUM" if score >= 1 / 3 else "WEAK")
        breakout = {"side": name, "level": level_name, "value": round(level_value, 2),
                    "distance": round(distance, 2),
                    "distance_sigma": round(distance / (price * sigma + EPS), 2),
                    "reach": round(min(reach, 99.0), 2), "score": round(score, 3),
                    "strength": label}

    # Grafik için: fiyatın iki yanındaki seviyeler, yakından uzağa.
    span = max(expected_move * 3, price * sigma * math.sqrt(session_bars))
    ladder = [{"level": name, "value": round(value, 2),
               "side": "resistance" if value > price else "support",
               "distance_pct": round((value / price - 1) * 100, 3),
               "sources": sources.get(name, [name])}
              for name, value in sorted(levels.items(), key=lambda kv: kv[1])
              if abs(value - price) <= span]

    def describe(item):
        if not item:
            return None
        name, value = item
        return {"level": name, "value": round(value, 2),
                "distance": round(abs(value - price), 2),
                "distance_pct": round((value / price - 1) * 100, 3),
                "distance_sigma": round(abs(value - price) / (price * sigma + EPS), 2),
                "sources": sources.get(name, [name])}

    return {
        "as_of": bars[-1].t.isoformat(),
        "price": round(price, 2),
        "direction": direction,
        "strength": strength,
        "trend": trend,
        "support": describe(support),
        "resistance": describe(resistance),
        "outside_ladder": outside,
        "touching": describe(touching),
        "breakout": breakout,
        # Grafiğin çizdiği merdiven. Fiyata yakın olanlar önce gelir; uzaktaki
        # haftalık uçlar (S3/R3) çizimde fiyat çizgisini ezmesin diye kırpılır.
        "ladder": ladder,
        "components": {key: round(value, 3) for key, value in parts.items()
                       if key != "previous_velocity"} |
                      ({"volume": round(volume_z, 3)} if volume_z is not None else {}),
        "session": {
            "bars": len(session), "expected_bars": session_bars, "remaining_bars": remaining,
            "volatility_pct": round(sigma * 100, 4),
            "expected_move": round(expected_move, 2),
            "has_volume": volume_z is not None,
            "t_stat": round(t_stat, 3),
        },
    }
