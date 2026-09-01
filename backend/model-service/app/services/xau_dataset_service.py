"""XAU/USD hedefli, geleceğe sızıntısız günlük eğitim veri seti üretimi."""

from __future__ import annotations

import csv
import io
import logging
import math
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import fmean, pstdev

log = logging.getLogger(__name__)

XAU_HISTORY_URL = "https://xaus.com/api/v1/history"
# Yedek kaynak: birincil kaynak 2026-08-31'de 503 vermeye başladı ve saatlik
# job "HTTP Error 503" ile düştü; veri seti donup kaldı. Yahoo'nun altın vadeli
# serisi aynı alanları ve aynı uzunlukta geçmişi veriyor. Vadeli fiyat spot'tan
# ~%0,6 farklı; girdilerin tamamı getiri/oran olduğu için model bundan
# etkilenmez ve seri tek kaynaktan geldiği için kendi içinde tutarlıdır.
XAU_FALLBACK_URL = ("https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
                    "?range=5y&interval=1d")
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
HORIZONS = (7, 14, 30)
FRED_IDS = ("DGS10", "DGS2", "DFII10", "DTWEXBGS", "DCOILWTICO", "VIXCLS", "CPILFESL")

FEATURES = (
    "gold_return_1d", "gold_return_5d", "gold_return_20d", "gold_ma_ratio_50d",
    "gold_rsi14_centered", "gold_atr14_pct", "gold_volatility_20d", "gold_drawdown_60d",
    "real_yield_change_5d", "real_yield_change_20d", "dollar_return_5d",
    "dollar_return_20d", "breakeven_change_20d", "yield_curve_10y_2y",
    "vix_level", "vix_change_5d", "core_cpi_yoy", "oil_return_5d", "oil_return_20d",
)


@dataclass(frozen=True)
class XauBar:
    day: date
    high: float
    low: float
    close: float


class Series:
    def __init__(self, points: list[tuple[date, float]]) -> None:
        points.sort()
        self.days = [point[0] for point in points]
        self.values = [point[1] for point in points]

    def as_of(self, day: date) -> float | None:
        index = bisect_right(self.days, day) - 1
        return self.values[index] if index >= 0 else None

    def change(self, day: date, days: int) -> float | None:
        current, previous = self.as_of(day), self.as_of(day - timedelta(days=days))
        return None if current is None or previous is None else current - previous

    def ratio(self, day: date, days: int) -> float | None:
        current, previous = self.as_of(day), self.as_of(day - timedelta(days=days))
        return None if current is None or previous in (None, 0) else current / previous - 1


def parse_fred(text: str) -> Series:
    points: list[tuple[date, float]] = []
    for row in csv.DictReader(io.StringIO(text)):
        values = list(row.values())
        try:
            points.append((date.fromisoformat(values[0]), float(values[-1])))
        except (IndexError, TypeError, ValueError):
            continue
    return Series(points)


def _gold_features(bars: list[XauBar], index: int) -> dict[str, float] | None:
    if index < 60:
        return None
    closes = [bar.close for bar in bars]
    changes = [closes[i] - closes[i - 1] for i in range(index - 13, index + 1)]
    gains = fmean(max(0.0, value) for value in changes)
    losses = fmean(max(0.0, -value) for value in changes)
    rsi = 100 - 100 / (1 + gains / (losses or 1e-9))
    returns = [math.log(closes[i] / closes[i - 1]) for i in range(index - 19, index + 1)]
    true_ranges = [max(bars[i].high - bars[i].low,
                       abs(bars[i].high - closes[i - 1]), abs(bars[i].low - closes[i - 1]))
                   for i in range(index - 13, index + 1)]
    return {
        "gold_return_1d": closes[index] / closes[index - 1] - 1,
        "gold_return_5d": closes[index] / closes[index - 5] - 1,
        "gold_return_20d": closes[index] / closes[index - 20] - 1,
        "gold_ma_ratio_50d": closes[index] / fmean(closes[index - 49:index + 1]) - 1,
        "gold_rsi14_centered": (rsi - 50) / 50,
        "gold_atr14_pct": fmean(true_ranges) / closes[index],
        "gold_volatility_20d": pstdev(returns) * math.sqrt(252),
        "gold_drawdown_60d": closes[index] / max(closes[index - 59:index + 1]) - 1,
    }


def _macro_features(series: dict[str, Series], day: date) -> dict[str, float] | None:
    dgs10, dgs2, real = (series[key].as_of(day) for key in ("DGS10", "DGS2", "DFII10"))
    old_day = day - timedelta(days=20)
    old_10, old_real = series["DGS10"].as_of(old_day), series["DFII10"].as_of(old_day)
    values = {
        "real_yield_change_5d": series["DFII10"].change(day, 5),
        "real_yield_change_20d": series["DFII10"].change(day, 20),
        "dollar_return_5d": series["DTWEXBGS"].ratio(day, 5),
        "dollar_return_20d": series["DTWEXBGS"].ratio(day, 20),
        "breakeven_change_20d": None if None in (dgs10, real, old_10, old_real) else (dgs10 - real) - (old_10 - old_real),
        "yield_curve_10y_2y": None if dgs10 is None or dgs2 is None else dgs10 - dgs2,
        "vix_level": series["VIXCLS"].as_of(day),
        "vix_change_5d": series["VIXCLS"].change(day, 5),
        "core_cpi_yoy": None,
        "oil_return_5d": series["DCOILWTICO"].ratio(day, 5),
        "oil_return_20d": series["DCOILWTICO"].ratio(day, 20),
    }
    cpi_now, cpi_old = series["CPILFESL"].as_of(day), series["CPILFESL"].as_of(day - timedelta(days=365))
    if cpi_now is not None and cpi_old not in (None, 0):
        values["core_cpi_yoy"] = (cpi_now / cpi_old - 1) * 100
    return None if any(value is None for value in values.values()) else values  # type: ignore[return-value]


def build_rows(bars: list[XauBar], series: dict[str, Series]) -> list[dict[str, float | str]]:
    """O gün bilinen girdileri her ufkun sonraki ilk işlem günüyle hizalar.

    Güncel özellik satırları korunur; henüz gerçekleşmemiş hedefler ufuk bazında
    boş bırakılır ve yalnız ilgili modelin eğitimi sırasında dışarıda tutulur.
    """
    days = [bar.day for bar in bars]
    rows: list[dict[str, float | str]] = []
    for index, bar in enumerate(bars):
        gold, macro = _gold_features(bars, index), _macro_features(series, bar.day)
        if gold is None or macro is None:
            continue
        targets = {}
        for horizon in HORIZONS:
            target_index = bisect_right(days, bar.day + timedelta(days=horizon - 1))
            targets[f"target_return_{horizon}d"] = (
                "" if target_index >= len(bars) else bars[target_index].close / bar.close - 1)
        rows.append({"date": bar.day.isoformat(), "xauusd_close": bar.close, **gold, **macro, **targets})
    return rows


def yahoo_bars(payload: dict) -> list[XauBar]:
    """Yahoo grafik yanıtını günlük barlara çevirir; eksik günler atlanır."""
    results = (payload.get("chart") or {}).get("result") or []
    if not results:
        raise ValueError("Yedek altın kaynağı beklenen gövdeyi döndürmedi")
    result = results[0]
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    bars = []
    for stamp, close, high, low in zip(result.get("timestamp") or [], quote.get("close", []),
                                       quote.get("high", []), quote.get("low", [])):
        if close is None or high is None or low is None:
            continue
        day = datetime.fromtimestamp(stamp, timezone.utc).date()
        bars.append(XauBar(day, float(high), float(low), float(close)))
    if not bars:
        raise ValueError("Yedek altın kaynağında kullanılabilir gün yok")
    bars.sort(key=lambda bar: bar.day)
    return bars


def fetch_bars(requests) -> list[XauBar]:
    """Birincil kaynak; erişilemezse yedeğe düşer."""
    try:
        response = requests.get(XAU_HISTORY_URL, impersonate="chrome", timeout=30)
        response.raise_for_status()
        payload = response.json()
        return [XauBar(date.fromisoformat(row["d"]), float(row["h"]), float(row["l"]), float(row["c"]))
                for row in payload["points"]]
    except Exception as error:
        log.warning("Birincil altın kaynağı erişilemedi (%s); yedeğe düşülüyor", error)
        fallback = requests.get(XAU_FALLBACK_URL, impersonate="chrome", timeout=30)
        fallback.raise_for_status()
        return yahoo_bars(fallback.json())


def fetch_dataset() -> list[dict[str, float | str]]:
    from curl_cffi import requests
    bars = fetch_bars(requests)
    start = (bars[0].day - timedelta(days=400)).isoformat()
    macro: dict[str, Series] = {}
    for series_id in FRED_IDS:
        fred = requests.get(FRED_URL, params={"id": series_id, "cosd": start}, impersonate="chrome", timeout=30)
        fred.raise_for_status()
        macro[series_id] = parse_fred(fred.text)
    return build_rows(bars, macro)


def write_csv(path) -> int:
    rows = fetch_dataset()
    if not rows:
        raise RuntimeError("XAU/USD eğitim satırı üretilemedi")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
