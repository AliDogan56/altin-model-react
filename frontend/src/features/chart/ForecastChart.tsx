import { useId, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { HORIZON_LABELS } from '../../content/site';
import { model } from '../../data/artifact';
import { computeDomain, dropNear, pickTimeTicks } from '../../domain/chart/scale';
import { BAND_COVERAGE, buildDailyPath } from '../../domain/model/predict';
import type { Forecast } from '../../domain/model/types';
import { findLevels } from '../../domain/supportResistance';
import { longDate, money, shortDate } from '../../lib/format';
import { useChartGestures } from './useChartGestures';
import { useElementSize } from './useElementSize';

/** Dar yerleşim eşiği; CSS'teki kırılma noktasıyla aynı olmalı (`_chart-extras.scss`).
 *  Önceden JS 720px'te, CSS 650px'te ayrılıyordu; arada kalan genişliklerde
 *  mobil viewBox masaüstü kutusuna oturup genişliğin üçte biri boş kalıyordu. */
const COMPACT_WIDTH = 650;
const WIDE = { l: 60, r: 104, t: 20, b: 54 };
/** Dar ekranda y etiketleri çizim alanının içine alınır, sol kenar boşluğu 10px'e iner. */
const COMPACT = { l: 10, r: 78, t: 14, b: 48 };
const MAX_ZOOM = 6;
const YEAR_LABEL_SPAN = 200;   // bu kadar günden geniş aralıkta etikete yıl eklenir

type ChartProps = {
  forecast: Forecast; originForecast: Forecast;
  history: [string, number][];
  rangeDays: number; horizonDays: number;
  showBand: boolean; showLevels: boolean; showOrigin: boolean; showSR: boolean;
  onToggle: (key: 'band' | 'levels' | 'origin' | 'sr') => void;
  levels: { buy: [number, number]; sell: [number, number]; stop: number };
  spot: { price: number }; tokenSpot: { price: number };
  /** Grafiğin metin karşılığı olan tablonun id'si; ekran okuyucu oraya yönlendirilir. */
  describedById?: string;
};

type Point = { i: number; v: number; date: string; kind: string; lo?: number; hi?: number };

function ForecastChart({
  forecast, history, rangeDays, horizonDays, showBand, showLevels, showOrigin, showSR,
  originForecast, onToggle, levels, spot, tokenSpot, describedById,
}: ChartProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  /* Ölçüm SVG'nin kendisinde değil saran div'de yapılır: ResizeObserver
     <svg> elemanı için hiç tetiklenmiyor (deneyle doğrulandı), div'de sorunsuz. */
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

  /* Kimliği sabit tutulur: imleç her kımıldadığında destek/direnç yeniden hesaplanmasın. */
  const hist = useMemo<Point[]>(() => {
    const shown = history.slice(-rangeDays);
    return shown.map((d, i) => ({ i: i - (shown.length - 1), v: d[1], date: d[0], kind: 'Geçmiş' }));
  }, [history, rangeDays]);
  const lastHistoryDate = hist.length ? hist[hist.length - 1].date : undefined;
  const future = buildDailyPath(model, forecast, horizonDays, lastHistoryDate)
    .map(d => ({ ...d, i: d.day, kind: d.day === 0 ? 'Bugün' : `${d.day}. gün` }));
  const anchorDays = [0, 30, 90, 180].filter(d => d <= horizonDays);

  /* Destek/direnç: görünen geçmişteki dönüş noktaları kümelenir, en çok dokunulan
     dördü çizilir. Fiyatın üstündekiler direnç, altındakiler destektir. */
  const srLevels = useMemo(() => findLevels(hist.map(d => d.v)), [hist]);

  /* Modelin ilk yayınladığı tahmin (model.latestDate) o günkü girdilerle hesaplanıp
     geçmişe oturtulur; amacı vadesi gelmiş günlerde tahmini gerçekleşenle karşılaştırmaktır. */
  const originAt = hist.find(d => d.date === model.latestDate);
  /* Projeksiyon katman kapalıyken de hesaplanır: geçmiş günlerin ipucundaki
     "o gün ne demiştik / ne oldu" karşılaştırması efsane düğmesine bağlı kalmasın. */
  const originProjection = useMemo(() => (originAt
    ? buildDailyPath(model, { ...originForecast, price: model.latestPrice }, horizonDays, model.latestDate)
        .map(d => ({ ...d, i: originAt.i + d.day }))
    : null), [originAt?.i, originForecast, horizonDays]);
  const originPath = showOrigin ? originProjection : null;
  const originByDate = useMemo(() => new Map(
    (originProjection ?? []).map(d => [d.date, d])), [originProjection]);

  const resistance = Math.max(model.resistance.r20, model.resistance.r60)
    * (forecast.price / model.latestPrice) * (1 + model.resistance.momentumJumpPct);

  const startI = -(hist.length - 1), endI = horizonDays;
  const totalSpan = endI - startI, visibleSpan = totalSpan / zoom;
  const center = Math.max(startI + visibleSpan / 2,
    Math.min(endI - visibleSpan / 2, (startI + endI) / 2 + panDays));
  const visibleStart = center - visibleSpan / 2, visibleEnd = center + visibleSpan / 2;

  /* Dikey ölçek: bant çekirdek serileri ezmesin diye pay sınırıyla dahil edilir. */
  const core = [
    ...hist.map(d => d.v), ...future.map(d => d.v), spot.price, tokenSpot.price,
    ...(originPath ? originPath.map(d => d.v) : []),
    ...(showSR ? srLevels.map(l => l.price) : []),
    ...(showLevels ? [...levels.buy, ...levels.sell, levels.stop, resistance] : []),
  ];
  const bandValues = showBand ? future.flatMap(d => [d.lo, d.hi]) : [];
  const domain = computeDomain(core, bandValues);

  const x = (i: number) => m.l + (i - visibleStart) / (visibleEnd - visibleStart) * plotW;
  const y = (v: number) => m.t + (domain.max - v) / (domain.max - domain.min) * plotH;
  const line = (points: { i: number; v: number }[]) => points.map(d => `${x(d.i)},${y(d.v)}`).join(' ');
  const bandShape = `${future.map(d => `${x(d.i)},${y(d.hi)}`).join(' ')} `
    + `${[...future].reverse().map(d => `${x(d.i)},${y(d.lo)}`).join(' ')}`;

  /* i değerleri benzersiz olmalı: eskiden köken projeksiyonu ile geçmiş aynı i'yi
     paylaşıyor, eşitlikte projeksiyon kazanıyordu; geçmiş bir günün gerçek kapanışı
     ipucunda hiç görünmüyordu. Bugün (i=0) gerçekleşen tarafa aittir. */
  const probePoints: Point[] = [...hist, ...future.slice(1)];
  const dateByIndex = useMemo(() => {
    const map = new Map<number, string>();
    hist.forEach(d => map.set(d.i, d.date));
    future.forEach(d => map.set(d.i, d.date));
    return map;
  }, [hist, lastHistoryDate, horizonDays]);

  /* Zaman ekseni: aralığa uyan tarih etiketleri + ufuk çıpaları. Önceden eksende
     yalnız "−90 gün / Bugün / 1 Ay" yazıyordu, geçmişte tek bir tarih yoktu. */
  const withYear = visibleSpan > YEAR_LABEL_SPAN;
  const anchorGap = Math.max(2, visibleSpan * 0.08);
  const visibleAnchors = anchorDays.filter(d => d >= visibleStart && d <= visibleEnd);
  const timeTicks = [
    ...visibleAnchors.map(i => ({ i, anchor: true })),
    ...visibleAnchors
      .reduce((ticks, a) => dropNear(ticks, a, anchorGap),
        pickTimeTicks(visibleStart, visibleEnd, compact ? 4 : 7))
      .map(i => ({ i, anchor: false })),
  ].sort((a, b) => a.i - b.i);

  const tickLabel = (i: number, anchor: boolean) => {
    if (i === 0) return 'Bugün';
    const date = dateByIndex.get(i);
    if (!date) return null;
    const label = shortDate(date, withYear);
    return anchor && !compact ? `${label} · ${HORIZON_LABELS[i] ?? ''}`.trim() : label;
  };

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

  /* Klavye ile imleç gezinme: grafik odaklanabilir, ok tuşları gün gün ilerletir.
     Nokta görünür pencerenin dışına çıkarsa pencere ona kayar. */
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
      PageUp: () => step(-30),
      PageDown: () => step(30),
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
  const summary = `Sol tarafta son ${hist.length} günün gerçekleşen ons altın kapanışı, `
    + `sağ tarafta ${horizonDays} günlük model tahmini ve %${BAND_COVERAGE} belirsizlik bandı. `
    + `Güncel fiyat ${money(spot.price)}. ${horizonDays} gün sonrası için tahmin ${money(last.v)}, `
    + `olası aralık ${money(last.lo)} ile ${money(last.hi)} arası.`;
  const spoken = !hover ? '' : Number.isFinite(hover.lo)
    ? `${longDate(hover.date)}: tahmin ${money(hover.v)}, olası aralık ${money(hover.lo!)} ile ${money(hover.hi!)} arası.`
    : `${longDate(hover.date)}: gerçekleşen ${money(hover.v)}.`;

  const zone = (a: number, b: number, className: string) =>
    <rect className={className} x={m.l} y={y(Math.max(a, b))} width={plotW}
          height={Math.max(2, Math.abs(y(a) - y(b)))}/>;

  const cardW = compact ? 72 : 96;
  const reset = () => { setZoom(1); setPanDays(0); };

  return <div className="chart-wrap">
    <div className="zoom-controls">
      <span>Yakınlaştırma {zoom.toFixed(1)}×</span>
      <button onClick={() => setPanDays(v => v - visibleSpan * .22)} disabled={zoom === 1} aria-label="Geri kaydır">←</button>
      <button onClick={() => zoomBy(1 / 1.5)} disabled={zoom === 1} aria-label="Uzaklaştır">−</button>
      <button onClick={() => zoomBy(1.5)} disabled={zoom >= MAX_ZOOM} aria-label="Yakınlaştır">+</button>
      <button onClick={() => setPanDays(v => v + visibleSpan * .22)} disabled={zoom === 1} aria-label="İleri kaydır">→</button>
      <button className="zoom-reset" onClick={reset} disabled={zoom === 1} aria-label="Yakınlaştırmayı sıfırla">
        <span aria-hidden="true">⟲</span><em>Sıfırla</em>
      </button>
    </div>

    <div className="chart-canvas" ref={boxRef}>
    <svg ref={svgRef} className={`chart ${compact ? 'compact' : ''}`} viewBox={`0 0 ${W} ${H}`}
         role="img" aria-labelledby={`${clipId}-title ${clipId}-desc`} aria-describedby={describedById}
         tabIndex={0} onKeyDown={onKeyDown} {...gestures}>
      <title id={`${clipId}-title`}>Ons altın: gerçekleşen fiyat ve model tahmini</title>
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

          {showSR && srLevels.map(level => <g key={level.price} className={`sr ${level.price >= spot.price ? 'res' : 'sup'}`}>
            <line x1={m.l} y1={y(level.price)} x2={x(0)} y2={y(level.price)}/>
            <text x={x(0) - 4} y={y(level.price) - 4} textAnchor="end">
              {money(level.price)}{!compact && ` · ${level.touches} dokunuş`}</text>
          </g>)}

          {showLevels && <>
            {zone(levels.buy[0], levels.buy[1], 'buy-zone')}
            {zone(levels.sell[0], levels.sell[1], 'sell-zone')}
            <line className="stop-line" x1={m.l} y1={y(levels.stop)} x2={W - m.r} y2={y(levels.stop)}/>
            <text className="stop-label" x={m.l + 5} y={y(levels.stop) - 5}>Risk kesme {money(levels.stop)}</text>
            <line className="resistance" x1={W - m.r - 70} y1={y(resistance)} x2={W - m.r} y2={y(resistance)}/>
            <text className="guide" x={W - m.r - 74} y={y(resistance) + 3} textAnchor="end">
              Momentum eşiği {money(resistance)}</text>
          </>}

          {showBand && <polygon className="band" points={bandShape}/>}
          {originPath && <polyline className="origin-forecast" points={line(originPath)}/>}
          <polyline className="history" points={line(hist)}/>
          <polyline className="forecast" points={line(future)}/>
          <line className="now-line" x1={m.l} y1={y(spot.price)} x2={W - m.r} y2={y(spot.price)}/>

          {anchorDays.map((day, k) => <circle key={day} cx={x(day)} cy={y(future[day].v)}
                r={k ? 5 : 4} className={k ? 'future-dot' : 'today-dot'}/>)}
          <circle className="now-dot-ons" cx={x(0)} cy={y(spot.price)} r="6"/>
          <circle className="now-dot-token" cx={x(0)} cy={y(tokenSpot.price)} r="4"/>
        </g>

        <line className="today-divider" x1={x(0)} y1={m.t} x2={x(0)} y2={H - m.b}/>
        {!compact && <>
          <text className="zone-caption" x={x(0) - 8} y={m.t + 13} textAnchor="end">gerçekleşen</text>
          <text className="zone-caption" x={x(0) + 8} y={m.t + 13}>tahmin</text>
        </>}
        {originPath && originAt && <>
          <line className="origin-marker" x1={x(originAt.i)} y1={m.t} x2={x(originAt.i)} y2={H - m.b}/>
          <text className="origin-label" x={x(originAt.i) + 5} y={m.t + (compact ? 13 : 28)}>
            {compact ? originLabel : `Model başlangıcı ${originLabel}`}</text>
        </>}

        <g transform={`translate(${W - m.r + 5} ${Math.min(H - m.b - 44, Math.max(m.t, y(spot.price) - 22))})`}>
          <rect className="now-card" width={cardW} height="44" rx="9"/>
          <text className="now-tag" x="7" y="13">ONS</text>
          <text className="now-value" x={cardW - 7} y="13" textAnchor="end">{money(spot.price)}</text>
          <text className="now-tag alt" x="7" y="33">PAXG</text>
          <text className="now-value alt" x={cardW - 7} y="33" textAnchor="end">{money(tokenSpot.price)}</text>
        </g>

        {timeTicks.map(({ i, anchor }) => {
          const label = tickLabel(i, anchor);
          return label && <text key={i} className={`axis time${anchor ? ' anchor' : ''}`}
                x={Math.min(W - m.r, Math.max(m.l, x(i)))} y={H - m.b + 18} textAnchor="middle">{label}</text>;
        })}
        {!compact && <text className="axis-title" transform={`translate(16 ${H / 2}) rotate(-90)`}
              textAnchor="middle">USD / ons</text>}
        {showBand && domain.bandClipped &&
          <text className="band-clip-note" x={W - m.r} y={m.t - 5} textAnchor="end">
            bant uçları kırpıldı · tam değerler ipucunda</text>}

        {hover && (() => {
          const isForecast = Number.isFinite(hover.lo) && Number.isFinite(hover.hi);
          /* Geçmiş gün: gerçekleşen kapanış + o gün model ne demişti. */
          const said = isForecast ? undefined : originByDate.get(hover.date);
          const errorPct = said ? (said.v - hover.v) / hover.v : null;
          const boxW = isForecast ? (compact ? 196 : 236) : said ? (compact ? 196 : 226) : (compact ? 150 : 172);
          const boxH = isForecast ? 92 : said ? 106 : 48;
          /* Sabitlenmiş (dokunmatik) ipucu parmağın altında kalmasın diye
             çizim alanının üst köşesine, dokunulan taraftan uzağa yerleşir. */
          const cornerX = x(hover.i) < W / 2 ? W - m.r - boxW - 6 : m.l + 6;
          const boxX = pinned ? cornerX : Math.min(W - m.r - boxW - 6, Math.max(m.l + 5, x(hover.i) + 12));
          const boxY = pinned ? m.t + 6 : Math.min(H - m.b - boxH - 6, Math.max(10, y(hover.v) - boxH / 2));
          return <g className="crosshair">
            <line x1={x(hover.i)} y1={m.t} x2={x(hover.i)} y2={H - m.b}/>
            {isForecast && showBand && <>
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
                <text x="11" y="40" className="tip-min">Olası minimum (%{BAND_COVERAGE})</text>
                <text x={boxW - 11} y="40" textAnchor="end" className="tip-value tip-min">{money(hover.lo!)}</text>
                <text x="11" y="61" className="tip-price">Sinir ağı tahmini</text>
                <text x={boxW - 11} y="61" textAnchor="end" className="tip-value tip-price">{money(hover.v)}</text>
                <text x="11" y="82" className="tip-max">Olası maksimum (%{BAND_COVERAGE})</text>
                <text x={boxW - 11} y="82" textAnchor="end" className="tip-value tip-max">{money(hover.hi!)}</text>
              </> : <>
                <text x="11" y="40" className="tip-real">Gerçekleşen</text>
                <text x={boxW - 11} y="40" textAnchor="end" className="tip-value tip-real">{money(hover.v)}</text>
                {said && <>
                  <line className="tip-divider" x1="11" y1="53" x2={boxW - 11} y2="53"/>
                  <text x="11" y="71" className="tip-price">{originLabel} tahmini</text>
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
      <span><i className="history-key"/>Gerçekleşen</span>
      <span><i className="forecast-key"/>Model tahmini</span>
      <button type="button" className={showBand ? 'on' : 'off'} aria-pressed={showBand} onClick={() => onToggle('band')}>
        <i className="band-key"/>%{BAND_COVERAGE} bant</button>
      <button type="button" className={showOrigin ? 'on' : 'off'} aria-pressed={showOrigin}
              disabled={!originAt} title={originAt ? undefined : `${originLabel} seçili geçmiş aralığında değil`}
              onClick={() => onToggle('origin')}>
        <i className="origin-key"/>{originLabel} tahmini</button>
      <button type="button" className={showSR ? 'on' : 'off'} aria-pressed={showSR} onClick={() => onToggle('sr')}>
        <i className="sr-key"/>Destek / direnç</button>
      <button type="button" className={showLevels ? 'on' : 'off'} aria-pressed={showLevels} onClick={() => onToggle('levels')}>
        <i className="buy-key"/>İşlem bölgeleri</button>
    </div>
    <p className="sr-live" role="status" aria-live="polite">{spoken}</p>
    <p className="chart-hint">
      {compact ? 'Sürükleyerek kaydır · iki parmakla yakınlaştır · dokununca değerler sabitlenir'
               : 'Sürükleyerek kaydır · tekerlekle yakınlaştır · üzerine gelince değerler görünür · odaklanınca ok tuşlarıyla gezin'}
    </p>
  </div>;
}

export default ForecastChart;
