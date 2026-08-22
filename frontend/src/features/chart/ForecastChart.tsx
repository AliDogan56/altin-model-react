import { useId, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { model } from '../../data/artifact';
import { computeDomain, dropNear, pickTimeTicks } from '../../domain/chart/scale';
import { BAND_COVERAGE, buildDailyPath } from '../../domain/model/predict';
import type { Forecast } from '../../domain/model/types';
import type { LadderItem } from '../../domain/pivots';
import { longDate, money, shortDate } from '../../lib/format';
import { useChartGestures } from './useChartGestures';
import { useElementSize } from './useElementSize';

/** Dar yerleşim eşiği; CSS'teki kırılma noktasıyla aynı olmalı (`_chart-extras.scss`). */
const COMPACT_WIDTH = 650;
const WIDE = { l: 58, r: 96, t: 18, b: 50 };
/** Dar ekranda y etiketleri çizim alanının içine alınır. */
const COMPACT = { l: 10, r: 74, t: 14, b: 46 };
const MAX_ZOOM = 6;
const YEAR_LABEL_SPAN = 200;
/** Destek/direnç bir nokta değil bölgedir; fiyatın bu kadar altı ve üstü. */
const ZONE_HALF_WIDTH = 0.0025;
/** S1/R1 en önemli, S3/R3 en uzak; çizgi belirginliği buna göre kademelenir. */
const EMPHASIS: Record<string, string> = { P: 'pivot', R1: 'near', S1: 'near', R2: 'mid', S2: 'mid', R3: 'far', S3: 'far' };

type ChartProps = {
  forecast: Forecast; originForecast: Forecast;
  available: boolean;
  history: [string, number][];
  rangeDays: number; horizonDays: number;
  showOrigin: boolean; onToggleOrigin: () => void;
  /** Pivot kartıyla **aynı** seviyeler; iki bölüm farklı sayı göstermesin. */
  levels: LadderItem[];
  levelPeriod: string;
  spot: { price: number };
  describedById?: string;
};

type Point = { i: number; v: number; date: string; kind: string; lo?: number; hi?: number };

function ForecastChart({
  forecast, originForecast, available, history, rangeDays, horizonDays,
  showOrigin, onToggleOrigin, levels, levelPeriod, spot, describedById,
}: ChartProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  /* Ölçüm SVG'de değil saran div'de: ResizeObserver <svg> için tetiklenmiyor. */
  const boxRef = useRef<HTMLDivElement | null>(null);
  const clipId = useId();
  const { width: W, height: H } = useElementSize(boxRef);
  const ready = W > 60 && H > 60;
  const compact = W < COMPACT_WIDTH;
  const m = compact ? COMPACT : WIDE;
  const plotW = Math.max(1, W - m.l - m.r);
  const plotH = Math.max(1, H - m.t - m.b);

  const [hover, setHover] = useState<Point | null>(null);
  const [pinned, setPinned] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [panDays, setPanDays] = useState(0);

  const hist = useMemo<Point[]>(() => {
    const shown = history.slice(-rangeDays);
    return shown.map((d, i) => ({ i: i - (shown.length - 1), v: d[1], date: d[0], kind: 'Geçmiş' }));
  }, [history, rangeDays]);
  const lastHistoryDate = hist.length ? hist[hist.length - 1].date : undefined;
  const future = buildDailyPath(model, forecast, horizonDays, lastHistoryDate)
    .map(d => ({ ...d, i: d.day, kind: d.day === 0 ? 'Bugün' : `${d.day}. gün` }));

  const originAt = model.fallback ? undefined : hist.find(d => d.date === model.latestDate);
  const originProjection = useMemo(() => (originAt
    ? buildDailyPath(model, { ...originForecast, price: model.latestPrice }, horizonDays, model.latestDate)
        .map(d => ({ ...d, i: originAt.i + d.day }))
    : null), [originAt?.i, originForecast, horizonDays]);
  const originPath = showOrigin ? originProjection : null;
  const originByDate = useMemo(() => new Map(
    (originProjection ?? []).map(d => [d.date, d])), [originProjection]);

  const startI = -(hist.length - 1), endI = horizonDays;
  const visibleSpan = (endI - startI) / zoom;
  const center = Math.max(startI + visibleSpan / 2,
    Math.min(endI - visibleSpan / 2, (startI + endI) / 2 + panDays));
  const visibleStart = center - visibleSpan / 2, visibleEnd = center + visibleSpan / 2;

  const core = [
    ...hist.map(d => d.v), ...(available ? future.map(d => d.v) : []), spot.price,
    ...(originPath ? originPath.map(d => d.v) : []),
  ];
  /* Pivot seviyeleri ve bant "kırpılabilir" kümede: S3/R3 fiyattan %10 uzakta
     olabiliyor, çekirdek kümeye konsa fiyat çizgisini düz bir hat yapardı. */
  const bandValues = [
    ...(available ? future.flatMap(d => [d.lo, d.hi]) : []),
    ...levels.map(l => l.value),
  ];
  const domain = computeDomain(core, bandValues);

  const x = (i: number) => m.l + (i - visibleStart) / (visibleEnd - visibleStart) * plotW;
  const y = (v: number) => m.t + (domain.max - v) / (domain.max - domain.min) * plotH;
  const line = (points: { i: number; v: number }[]) => points.map(d => `${x(d.i)},${y(d.v)}`).join(' ');
  const bandShape = `${future.map(d => `${x(d.i)},${y(d.hi)}`).join(' ')} `
    + `${[...future].reverse().map(d => `${x(d.i)},${y(d.lo)}`).join(' ')}`;

  const probePoints: Point[] = [...hist, ...(available ? future.slice(1) : [])];
  const dateByIndex = useMemo(() => {
    const map = new Map<number, string>();
    hist.forEach(d => map.set(d.i, d.date));
    future.forEach(d => map.set(d.i, d.date));
    return map;
  }, [hist, lastHistoryDate, horizonDays]);

  const withYear = visibleSpan > YEAR_LABEL_SPAN;
  const timeTicks = dropNear(
    pickTimeTicks(visibleStart, visibleEnd, compact ? 4 : 6), 0, Math.max(2, visibleSpan * 0.09));

  const zoomBy = (factor: number) => setZoom(current => {
    const next = Math.max(1, Math.min(MAX_ZOOM, current * factor));
    if (next === 1) setPanDays(0);
    return next;
  });
  const panByPixels = (dx: number) => setPanDays(p => p - dx * (visibleSpan / plotW));
  const probeAt = (clientX: number) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect || !probePoints.length) return;
    const px = (clientX - rect.left) / rect.width * W;
    const day = visibleStart + (px - m.l) / plotW * (visibleEnd - visibleStart);
    setHover(probePoints.reduce((a, b) => (Math.abs(b.i - day) < Math.abs(a.i - day) ? b : a)));
  };
  const gestures = useChartGestures({
    svgRef, zoomBy, panByPixels, probeAt,
    clearProbe: () => setHover(null), pin: setPinned, pinned,
  });

  const focusPoint = (point: Point) => {
    setHover(point);
    setPinned(true);
    if (point.i < visibleStart) setPanDays(d => d + (point.i - visibleStart));
    else if (point.i > visibleEnd) setPanDays(d => d + (point.i - visibleEnd));
  };
  const step = (delta: number) => {
    if (!probePoints.length) return;
    const current = hover ? probePoints.indexOf(hover) : probePoints.findIndex(p => p.i === 0);
    const next = Math.max(0, Math.min(probePoints.length - 1, (current < 0 ? 0 : current) + delta));
    focusPoint(probePoints[next]);
  };
  const onKeyDown = (event: KeyboardEvent<SVGSVGElement>) => {
    const keys: Record<string, () => void> = {
      ArrowLeft: () => step(event.shiftKey ? -7 : -1),
      ArrowRight: () => step(event.shiftKey ? 7 : 1),
      Home: () => focusPoint(probePoints[0]),
      End: () => focusPoint(probePoints[probePoints.length - 1]),
      Escape: () => { setHover(null); setPinned(false); },
    };
    const action = keys[event.key];
    if (!action) return;
    event.preventDefault();
    action();
  };

  const originLabel = shortDate(model.latestDate, true);
  const last = future[future.length - 1];
  const summary = available
    ? `Solda son ${hist.length} günün gerçekleşen ons altın kapanışı, sağda ${horizonDays} günlük `
      + `model tahmini ve %${BAND_COVERAGE} olasılık aralığı. Güncel fiyat ${money(spot.price)}. `
      + `${horizonDays} gün sonrası için beklenti ${money(last.v)}, aralık ${money(last.lo)}–${money(last.hi)}. `
      + `${levelPeriod} pivot seviyeleri: ` + levels.map(l => `${l.name} ${money(l.value)}`).join(', ') + '.'
    : `Son ${hist.length} günün gerçekleşen ons altın kapanışı. Model tahmini bekleniyor.`;
  const spoken = !hover ? '' : Number.isFinite(hover.lo)
    ? `${longDate(hover.date)}: beklenti ${money(hover.v)}, aralık ${money(hover.lo!)}–${money(hover.hi!)}.`
    : `${longDate(hover.date)}: gerçekleşen ${money(hover.v)}.`;

  const tagW = compact ? 68 : 88;

  return <div className="chart-wrap">
    <div className="chart-canvas" ref={boxRef}>
      <svg ref={svgRef} className={`chart ${compact ? 'compact' : ''}`} viewBox={`0 0 ${W} ${H}`}
           role="img" aria-labelledby={`${clipId}-title ${clipId}-desc`} aria-describedby={describedById}
           tabIndex={0} onKeyDown={onKeyDown} {...gestures}>
        <title id={`${clipId}-title`}>Ons altın fiyatı, model beklentisi ve önemli seviyeler</title>
        <desc id={`${clipId}-desc`}>{summary}</desc>

        {ready && <>
          <defs><clipPath id={clipId}><rect x={m.l} y={m.t} width={plotW} height={plotH}/></clipPath></defs>

          {[0, 1, 2, 3, 4].map(k => {
            const v = domain.min + (domain.max - domain.min) * k / 4;
            return <g key={k}>
              <line className="gridline" x1={m.l} y1={y(v)} x2={W - m.r} y2={y(v)}/>
              {compact
                ? <text className="axis inside" x={m.l + 4} y={y(v) - 4}>{Math.round(v).toLocaleString('tr-TR')}</text>
                : <text className="axis" x={m.l - 8} y={y(v) + 3} textAnchor="end">{Math.round(v).toLocaleString('tr-TR')}</text>}
            </g>;
          })}

          <g clipPath={`url(#${clipId})`}>
            <rect className="future-zone" x={Math.max(m.l, x(0))} y={m.t}
                  width={Math.max(0, W - m.r - Math.max(m.l, x(0)))} height={plotH}/>

            {/* Pivot seviyeleri: pivot kartındakiyle birebir aynı sayılar.
                S1/R1 belirgin, S3/R3 daha soluk; her biri kendi adıyla etiketli. */}
            {levels.map(level => {
              const inside = level.value >= domain.min && level.value <= domain.max;
              if (!inside) return null;
              const support = level.name.startsWith('S');
              const kind = level.name === 'P' ? 'pivot' : support ? 'sup' : 'res';
              const top = y(level.value * (1 + ZONE_HALF_WIDTH));
              const bottom = y(level.value * (1 - ZONE_HALF_WIDTH));
              return <g key={level.name} className={`sr-zone ${kind} ${EMPHASIS[level.name] ?? 'mid'}`}>
                <rect x={m.l} y={top} width={plotW} height={Math.max(3, bottom - top)}/>
                <line className="sr-mid" x1={m.l} y1={y(level.value)} x2={W - m.r} y2={y(level.value)}/>
                <text className="sr-label" x={m.l + 8} y={y(level.value) - 5}>
                  {level.name} · {money(level.value)}</text>
              </g>;
            })}

            {available && <polygon className="band" points={bandShape}/>}
            {originPath && <polyline className="origin-forecast" points={line(originPath)}/>}
            <polyline className="history" points={line(hist)}/>
            {available && <polyline className="forecast" points={line(future)}/>}
            <circle className="now-dot-ons" cx={x(0)} cy={y(spot.price)} r="5"/>
          </g>

          <line className="today-divider" x1={x(0)} y1={m.t} x2={x(0)} y2={H - m.b}/>
          <text className="today-caption" x={x(0)} y={m.t - 4} textAnchor="middle">bugün</text>

          <g transform={`translate(${W - m.r + 4} ${Math.min(H - m.b - 24, Math.max(m.t, y(spot.price) - 12))})`}>
            <rect className="now-card" width={tagW} height="24" rx="7"/>
            <text className="now-value" x={tagW / 2} y="16" textAnchor="middle">{money(spot.price)}</text>
          </g>

          {timeTicks.map(i => {
            const date = dateByIndex.get(i);
            return date && <text key={i} className="axis time"
                  x={Math.min(W - m.r, Math.max(m.l, x(i)))} y={H - m.b + 18} textAnchor="middle">
              {shortDate(date, withYear)}</text>;
          })}
          <text className="axis time anchor" x={x(0)} y={H - m.b + 18} textAnchor="middle">bugün</text>

          {hover && (() => {
            const isForecast = Number.isFinite(hover.lo) && Number.isFinite(hover.hi);
            const said = isForecast ? undefined : originByDate.get(hover.date);
            const errorPct = said ? (said.v - hover.v) / hover.v : null;
            const boxW = isForecast ? (compact ? 190 : 214) : said ? (compact ? 190 : 214) : (compact ? 146 : 166);
            const boxH = isForecast ? 92 : said ? 106 : 48;
            const cornerX = x(hover.i) < W / 2 ? W - m.r - boxW - 6 : m.l + 6;
            const boxX = pinned ? cornerX : Math.min(W - m.r - boxW - 6, Math.max(m.l + 5, x(hover.i) + 12));
            const boxY = pinned ? m.t + 6 : Math.min(H - m.b - boxH - 6, Math.max(10, y(hover.v) - boxH / 2));
            return <g className="crosshair">
              <line x1={x(hover.i)} y1={m.t} x2={x(hover.i)} y2={H - m.b}/>
              {isForecast && <>
                <line className="band-range" x1={x(hover.i)} y1={y(hover.hi!)} x2={x(hover.i)} y2={y(hover.lo!)}/>
                <circle className="band-max-dot" cx={x(hover.i)} cy={y(hover.hi!)} r="4"/>
                <circle className="band-min-dot" cx={x(hover.i)} cy={y(hover.lo!)} r="4"/>
              </>}
              {said && <circle className="said-dot" cx={x(hover.i)} cy={y(said.v)} r="4"/>}
              <circle cx={x(hover.i)} cy={y(hover.v)} r="6"/>
              <g className="time-badge" transform={`translate(${x(hover.i)} ${H - m.b + 6})`}>
                <rect x="-31" y="0" width="62" height="18" rx="5"/>
                <text y="13" textAnchor="middle">{shortDate(hover.date, withYear)}</text>
              </g>
              <g className="hover-card" transform={`translate(${boxX} ${boxY})`}>
                <rect width={boxW} height={boxH} rx="8"/>
                <text x="11" y="19">{longDate(hover.date)}</text>
                {isForecast ? <>
                  <text x="11" y="40" className="tip-min">En düşük ihtimal</text>
                  <text x={boxW - 11} y="40" textAnchor="end" className="tip-value tip-min">{money(hover.lo!)}</text>
                  <text x="11" y="61" className="tip-price">Beklenen</text>
                  <text x={boxW - 11} y="61" textAnchor="end" className="tip-value tip-price">{money(hover.v)}</text>
                  <text x="11" y="82" className="tip-max">En yüksek ihtimal</text>
                  <text x={boxW - 11} y="82" textAnchor="end" className="tip-value tip-max">{money(hover.hi!)}</text>
                </> : <>
                  <text x="11" y="40" className="tip-real">Gerçekleşen</text>
                  <text x={boxW - 11} y="40" textAnchor="end" className="tip-value tip-real">{money(hover.v)}</text>
                  {said && <>
                    <line className="tip-divider" x1="11" y1="53" x2={boxW - 11} y2="53"/>
                    <text x="11" y="71" className="tip-price">{originLabel} beklentisi</text>
                    <text x={boxW - 11} y="71" textAnchor="end" className="tip-value tip-price">{money(said.v)}</text>
                    <text x="11" y="92" className="tip-error">Sapma</text>
                    <text x={boxW - 11} y="92" textAnchor="end"
                          className={`tip-value ${Math.abs(errorPct!) <= .01 ? 'tip-error-ok' : 'tip-error-bad'}`}>
                      {errorPct! >= 0 ? '+' : ''}{(errorPct! * 100).toFixed(2)}%</text>
                  </>}
                </>}
              </g>
            </g>;
          })()}
        </>}
      </svg>
    </div>

    <div className="chart-legend">
      <span><i className="history-key"/>Gerçekleşen fiyat</span>
      <span className={available ? undefined : 'legend-unavailable'}>
        <i className="forecast-key"/>{available ? 'Model beklentisi' : 'Model bekleniyor'}</span>
      {available && <span><i className="band-key"/>%{BAND_COVERAGE} olasılık aralığı</span>}
      <span><i className="sr-key"/>{levelPeriod} pivot seviyeleri (S1–S3 / R1–R3)</span>
      {originProjection && <button type="button" className={showOrigin ? 'on' : 'off'}
          aria-pressed={showOrigin} onClick={onToggleOrigin}>
        <i className="origin-key"/>{originLabel} beklentisini göster</button>}
    </div>

    <p className="sr-live" role="status" aria-live="polite">{spoken}</p>
    <p className="chart-hint">
      {compact ? 'Parmakla kaydır · iki parmakla yakınlaştır · dokununca değerler sabitlenir'
               : 'Sürükleyerek kaydır · tekerlekle yakınlaştır · üzerine gelince o günün değerleri görünür'}
    </p>
  </div>;
}

export default ForecastChart;
