"""Boru hattı: ham servis yükleri → tek `TechnicalAnalysis` → DTO sözlüğü.

Bu modül saftır: ağ yok, saat yok (`now` parametre), önbellek yok. Sırayla
mumları normalize eder, oluşan günü atar, referans fiyatı seçer, göstergeleri,
seans bloğunu, pivot setlerini, yapısal bölgeleri, trendi, günlük momentumu ve
iki taraflı kırılımı hesaplar; `to_dict` bunu snake_case bir sözlüğe çevirir.

Tasarım kararları:
- Bölge adayları için pivotlar **görüntülenen** set değil sabit bir yapısal
  kümedir (haftalık klasik 7 seviye + aylık klasik P/S1/R1 + günlük klasik P).
  Böylece analiz sorgu parametresinden bağımsız kalır ve önbellek anahtarı
  pivot seçimini taşımaz; başlık merdiveni istek anında µs sürede kurulur.
- Kırılımın pivot yedeği de aynı sebeple varsayılan (haftalık klasik) merdivendir.
- Hiçbir blok HTTP hatası üretmez; hesaplanamayan blok açıklayıcı `status` taşır.
"""
from __future__ import annotations

import dataclasses as dc
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping, Sequence

from . import session as session_block
from .breakout import Breakout, analyze_breakout
from .candles import Candle, IntradayBar, Quality, normalize_daily, normalize_intraday
from .config import CONFIG, TechnicalConfig
from .indicators import IndicatorReading, atr as atr_series, latest_indicators, moving_average_table
from .levels import Levels, analyze_levels
from .momentum_daily import MomentumDaily, momentum_daily as compute_momentum_daily
from .pivots import Ladder, PivotMethod, PivotPeriod, PivotSet, build_ladder, compute_all
from .reference import ReferencePrice, choose_reference
from .trend import TrendRange, trend_block

STATUS_OK = "OK"
STATUS_NO_DATA = "NO_DATA"
STATUS_INSUFFICIENT = "INSUFFICIENT_DATA"
STATUS_FLAT = "FLAT_MARKET"
STATUS_INTRADAY_UNAVAILABLE = "INTRADAY_UNAVAILABLE"
STATUS_INTRADAY_STALE = "INTRADAY_STALE"
STATUS_SESSION_TOO_SHORT = "SESSION_TOO_SHORT"
STATUS_FLAT_SESSION = "FLAT_SESSION"
MARKET_OPEN, MARKET_CLOSED = "OPEN", "CLOSED"
BODY_DEFINITION = "prev_close_to_close"
NOT_A_PROBABILITY = "NOT_A_PROBABILITY"
BLOCKS = ("daily", "session", "indicators", "pivots", "levels", "momentum_daily", "breakout", "trend")
STRUCTURAL_PIVOTS = ((PivotPeriod.WEEKLY, ("R3", "R2", "R1", "P", "S1", "S2", "S3")),
                     (PivotPeriod.MONTHLY, ("R1", "P", "S1")),
                     (PivotPeriod.DAILY, ("P",)))


@dataclass(frozen=True)
class TechnicalAnalysis:
    generated_at: datetime
    today: date
    config_hash: str
    daily: tuple[Candle, ...]
    quality: Quality
    last_is_forming: bool
    daily_source: dict[str, Any]
    intraday: tuple[IntradayBar, ...] | None
    intraday_quality: Quality | None
    intraday_source: str | None
    reference: ReferencePrice
    daily_change: dict[str, Any] | None
    atr: float | None
    indicators: dict[str, IndicatorReading] | None
    moving_averages: list[dict] | None
    session: dict | None
    session_status: str
    session_error: str | None
    market_state: str | None
    session_date: date | None
    session_stale: bool
    pivot_sets: dict[PivotPeriod, dict[PivotMethod, PivotSet]]
    levels: Levels | None
    trend: dict[str, TrendRange]
    momentum_daily: MomentumDaily | None
    breakout: Breakout | None
    default_ladder: Ladder | None
    status: dict[str, str]


def analyze(daily_payload: Mapping[str, Any], intraday_payload: Mapping[str, Any] | None, *,
            now: datetime, cfg: TechnicalConfig = CONFIG) -> TechnicalAnalysis:
    now = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    today = now.date()
    status: dict[str, str] = {}

    # 1-2) günlük mumlar + oluşan gün
    all_daily, quality = normalize_daily(daily_payload.get("points") or [])
    daily = tuple(c for c in all_daily if c.date < today)
    last_is_forming = len(daily) != len(all_daily)
    status["daily"] = STATUS_NO_DATA if not daily else (STATUS_INSUFFICIENT if len(daily) < 2 else STATUS_OK)
    daily_source = {"daily": daily_payload.get("source"), "daily_price_source": daily_payload.get("price_source"),
                    "daily_fallback": bool(daily_payload.get("fallback", False))}

    # 3) gün içi
    intraday: tuple[IntradayBar, ...] | None = None
    intraday_quality: Quality | None = None
    intraday_source = None
    if intraday_payload and intraday_payload.get("bars"):
        bars, intraday_quality = normalize_intraday(intraday_payload["bars"])
        intraday = tuple(bars) or None
        intraday_source = intraday_payload.get("source")

    # 4) referans + günlük hareket
    reference = choose_reference(daily, intraday, instrument=cfg.instrument)
    daily_change = None
    if len(daily) >= 2:
        prev, last = daily[-2], daily[-1]
        daily_change = {"date": last.date, "previous_date": prev.date, "close": last.close,
                        "previous_close": prev.close, "usd": last.close - prev.close,
                        "pct": last.close / prev.close - 1 if prev.close else None}

    enough = len(daily) >= cfg.min_daily_rows
    # 5) göstergeler
    atr_value: float | None = None
    readings: dict[str, IndicatorReading] | None = None
    ma_table: list[dict] | None = None
    if enough:
        series = atr_series(daily, cfg.indicators.atr_period)
        atr_value = series[-1] if series and series[-1] is not None else None
        readings = latest_indicators(daily, cfg.indicators)
        ma_table = moving_average_table(daily, cfg.indicators)
        status["indicators"] = STATUS_OK if atr_value is not None else STATUS_INSUFFICIENT
    else:
        status["indicators"] = STATUS_INSUFFICIENT
    flat = enough and (atr_value is None or atr_value <= 1e-12)

    # 6) seans bloğu (matematik dokunulmadı; yalnız durum sarmalı)
    session_dict: dict | None = None
    session_error: str | None = None
    market_state: str | None = None
    session_date: date | None = None
    session_stale = False
    if intraday is None:
        status["session"] = STATUS_INTRADAY_UNAVAILABLE
    else:
        last_bar = intraday[-1]
        session_date = last_bar.time.astimezone(timezone.utc).date()
        market_state = MARKET_CLOSED if now - last_bar.time > timedelta(minutes=cfg.session_closed_after_min) else MARKET_OPEN
        session_stale = bool(daily) and session_date < daily[-1].date
        try:
            session_dict = session_block.momentum(list(intraday_payload["bars"]),  # type: ignore[index]
                                                  daily=list(daily_payload.get("points") or []))
            status["session"] = STATUS_INTRADAY_STALE if session_stale else STATUS_OK
        except ValueError as error:
            session_error = str(error)
            status["session"] = STATUS_FLAT_SESSION if "sıfır" in session_error else STATUS_SESSION_TOO_SHORT

    # 7) pivotlar
    pivot_sets = compute_all(daily, today, cfg.pivots, cfg.completion) if daily else {}
    weekly_classic = _pivot_set(pivot_sets, PivotPeriod.WEEKLY, PivotMethod.CLASSIC)
    status["pivots"] = weekly_classic.status if weekly_classic else STATUS_INSUFFICIENT

    # 8) günlük momentum (σ20 buradan gelir), 9) bölgeler
    momentum: MomentumDaily | None = None
    if enough and not flat:
        momentum = compute_momentum_daily(daily, cfg.momentum_daily, cfg.indicators)
        status["momentum_daily"] = momentum.status
    else:
        status["momentum_daily"] = STATUS_FLAT if flat else STATUS_INSUFFICIENT
    sigma = momentum.sigma if momentum and momentum.status == STATUS_OK else None

    levels: Levels | None = None
    default_ladder: Ladder | None = None
    if enough and not flat and reference.value is not None:
        levels = analyze_levels(daily, reference.value, pivot_levels=_structural_pivots(pivot_sets), sigma=sigma,
                                params=cfg.levels, indicator_params=cfg.indicators)
        status["levels"] = levels.status
        margin = levels.margin_usd if levels.margin_usd is not None else 0.0
        if weekly_classic and weekly_classic.levels:
            default_ladder = build_ladder(weekly_classic.levels, reference.value, margin_usd=margin, atr=atr_value, params=cfg.pivots)
    else:
        status["levels"] = STATUS_FLAT if flat else STATUS_INSUFFICIENT

    # 10) trend
    trend = trend_block(daily, today, cfg.trend) if daily else {}
    status["trend"] = STATUS_OK if trend and any(r.status == STATUS_OK for r in trend.values()) else STATUS_INSUFFICIENT

    # 11) kırılım
    breakout: Breakout | None = None
    if reference.value is not None and enough:
        breakout = analyze_breakout(reference=reference.value, atr=atr_value, levels=levels, pivot_ladder=default_ladder,
                                    session=session_dict if status["session"] in (STATUS_OK, STATUS_INTRADAY_STALE) else None,
                                    momentum_daily=momentum, params=cfg.breakout)
        status["breakout"] = breakout.status
    else:
        status["breakout"] = STATUS_INSUFFICIENT

    return TechnicalAnalysis(
        generated_at=now, today=today, config_hash=cfg.config_hash(), daily=daily, quality=quality,
        last_is_forming=last_is_forming, daily_source=daily_source, intraday=intraday, intraday_quality=intraday_quality,
        intraday_source=intraday_source, reference=reference, daily_change=daily_change, atr=atr_value,
        indicators=readings, moving_averages=ma_table, session=session_dict, session_status=status["session"],
        session_error=session_error, market_state=market_state, session_date=session_date, session_stale=session_stale,
        pivot_sets=pivot_sets, levels=levels, trend=trend, momentum_daily=momentum, breakout=breakout,
        default_ladder=default_ladder, status=status)


def headline(analysis: TechnicalAnalysis, method: PivotMethod, period: PivotPeriod,
             cfg: TechnicalConfig = CONFIG) -> tuple[PivotSet | None, Ladder | None]:
    """İstek anında seçilen setin merdiveni; temas marjı bölge motorunun ATR marjıdır."""
    chosen = _pivot_set(analysis.pivot_sets, period, method)
    if not chosen or not chosen.levels or analysis.reference.value is None:
        return chosen, None
    margin = analysis.levels.margin_usd if analysis.levels and analysis.levels.margin_usd is not None else 0.0
    return chosen, build_ladder(chosen.levels, analysis.reference.value, margin_usd=margin, atr=analysis.atr, params=cfg.pivots)


def select_blocks(include: Sequence[str] | None) -> set[str]:
    """İstenen blok kümesi; boş/None = hepsi. Bilinmeyen ad → ValueError.

    Hem `to_dict` hem HTTP kabuğu (`?include=`, 422) bu tek doğrulamayı
    kullanır; hata metni iki yerde ayrı yazılıp ayrışmasın diye buradadır.
    """
    wanted = set(include) if include else set(BLOCKS)
    unknown = wanted - set(BLOCKS)
    if unknown:
        raise ValueError(f"Bilinmeyen blok: {', '.join(sorted(unknown))}")
    return wanted


def to_dict(analysis: TechnicalAnalysis, *, pivot_method: PivotMethod = PivotMethod.CLASSIC,
            pivot_period: PivotPeriod = PivotPeriod.WEEKLY, include: Sequence[str] | None = None,
            cache: Mapping[str, Any] | None = None, cfg: TechnicalConfig = CONFIG) -> dict[str, Any]:
    wanted = select_blocks(include)
    ref = analysis.reference
    out: dict[str, Any] = {
        "version": cfg.version, "generated_at": analysis.generated_at, "config_hash": analysis.config_hash,
        "meta": {"cache": dict(cache) if cache else None, "blocks": sorted(wanted)},
        "status": dict(analysis.status),
        "reference": {"value": ref.value, "frame": ref.frame, "instrument": ref.instrument, "as_of": ref.as_of,
                      "daily_date": ref.daily_date, "daily_close": ref.daily_close, "status": ref.status, "note": ref.note,
                      "source": {**analysis.daily_source, "intraday": analysis.intraday_source}},
    }
    if "daily" in wanted:
        q = analysis.quality
        iq = analysis.intraday_quality
        candles = analysis.daily if not cfg.chart_days else analysis.daily[-cfg.chart_days:]
        prev_close = None
        rows = []
        # pc: bir önceki tamamlanmış mumun kapanışı (gövde referansı); dilim başında da doğru olsun diye tüm seriden
        by_date = {c.date: i for i, c in enumerate(analysis.daily)}
        for c in candles:
            i = by_date[c.date]
            prev_close = analysis.daily[i - 1].close if i > 0 else None
            rows.append([c.date.isoformat(), c.high, c.low, c.close, prev_close])
        out["daily"] = {
            "status": analysis.status["daily"], "body_definition": BODY_DEFINITION, "change": analysis.daily_change,
            "quality": {"rows": q.kept, "received": q.received, "rejected": q.dropped_invalid, "duplicates": q.dropped_duplicate,
                        "range_widened": q.range_widened, "zero_range": sum(1 for c in analysis.daily if c.high == c.low),
                        "last_is_forming": analysis.last_is_forming, "first_date": q.first_date, "last_date": analysis.daily[-1].date if analysis.daily else None,
                        "intraday_bars": iq.kept if iq else 0, "intraday_rejected": iq.dropped_invalid if iq else 0},
            "candles": rows,
        }
    if "session" in wanted:
        block: dict[str, Any] = {"status": analysis.session_status, "frame": "intraday_5m", "instrument": cfg.instrument,
                                 "stale": analysis.session_stale, "market_state": analysis.market_state,
                                 "session_date": analysis.session_date, "error": analysis.session_error}
        if analysis.session:
            block.update(analysis.session)
        out["session"] = block
    if "indicators" in wanted:
        rows = []
        if analysis.indicators:
            for key, r in analysis.indicators.items():
                rows.append({"key": key, "value": r.value, "state": r.state, "extra": dict(r.extra)})
        out["indicators"] = {"status": analysis.status["indicators"], "date": analysis.daily[-1].date if analysis.daily else None,
                             "bars": len(analysis.daily), "atr": analysis.atr, "rows": rows,
                             "moving_averages": analysis.moving_averages or []}
    if "pivots" in wanted:
        chosen, ladder = headline(analysis, pivot_method, pivot_period, cfg)
        out["pivots"] = {
            "status": analysis.status["pivots"], "pivot_method": pivot_method.value, "pivot_period": pivot_period.value,
            "min_candles": cfg.pivots.min_candles,
            "headline": {**_plain(chosen), "ladder": _ladder_dict(ladder, analysis)} if chosen else None,
            "sets": {p.value.lower(): {**{k: v for k, v in _plain(next(iter(ms.values()))).items() if k not in ("method", "levels")},
                                       **{m.value.lower(): [list(x) for x in s.levels] for m, s in ms.items()}}
                     for p, ms in analysis.pivot_sets.items()},
        }
    if "levels" in wanted:
        lv = analysis.levels
        out["levels"] = ({**_plain(lv), "zones": [_plain(z) for z in lv.zones]} if lv
                         else {"status": analysis.status["levels"], "zones": []})
    if "momentum_daily" in wanted:
        out["momentum_daily"] = _plain(analysis.momentum_daily) if analysis.momentum_daily else {"status": analysis.status["momentum_daily"]}
    if "breakout" in wanted:
        out["breakout"] = _plain(analysis.breakout) if analysis.breakout else {"status": analysis.status["breakout"], "note": NOT_A_PROBABILITY}
    if "trend" in wanted:
        out["trend"] = {"status": analysis.status["trend"],
                        "ranges": {rid: {**{k: v for k, v in _plain(r).items() if k != "rows"},
                                         "rows": [_plain(row) for row in r.rows]} for rid, r in analysis.trend.items()}}
    return _plain(out)


def _pivot_set(sets, period: PivotPeriod, method: PivotMethod) -> PivotSet | None:
    return sets.get(period, {}).get(method)


def _structural_pivots(sets) -> list[tuple[str, float]]:
    """Bölge adayı pivotları: sabit yapısal küme, görüntülenen setten bağımsız."""
    out: list[tuple[str, float]] = []
    for period, names in STRUCTURAL_PIVOTS:
        chosen = _pivot_set(sets, period, PivotMethod.CLASSIC)
        if not chosen or not chosen.levels:
            continue
        prefix = {PivotPeriod.WEEKLY: "W_", PivotPeriod.MONTHLY: "M_", PivotPeriod.DAILY: "D_"}[period]
        out.extend((prefix + name, value) for name, value in chosen.levels if name in names)
    return out


def _ladder_dict(ladder: Ladder | None, analysis: TechnicalAnalysis) -> dict | None:
    if ladder is None:
        return None
    zones = analysis.levels.zones if analysis.levels else ()
    items = []
    for item in ladder.items:
        zone_id = next((z.id for z in zones if z.low <= item.value <= z.high), None)
        items.append({**_plain(item), "zone_id": zone_id})
    return {**{k: v for k, v in _plain(ladder).items() if k != "items"}, "frame": analysis.reference.frame, "items": items}


def _plain(value: Any) -> Any:
    """Dataclass/enum/tarih → JSON'a hazır Python; kayan sayılar 6 ondalığa yuvarlanır."""
    if dc.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in dc.fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value.tzinfo else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {(k.value if isinstance(k, Enum) else k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, float):
        return round(value, 6)
    return value
