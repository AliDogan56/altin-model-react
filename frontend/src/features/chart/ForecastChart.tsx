import { useId, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { model } from '../../data/artifact';
import { FRAME, sourceLabel, type ReferenceFrame } from '../../content/technical';
import { computeDomain, dropNear, pickTimeTicks } from '../../domain/chart/scale';
import { resolveHorizon } from '../../domain/model/horizon';
import { intervalLabel, buildDailyPath } from '../../domain/model/predict';
import type { Forecast } from '../../domain/model/types';
import { longDate, money, shortDate } from '../../lib/format';
import type { LadderItem, Zone } from '../../services/api/technical';
import type { MarketCandle } from '../dashboard/useTechnical';
import { candleShapes, candleWidth } from './geometry';
import { useChartGestures } from './useChartGestures';
import { useElementSize } from './useElementSize';

/** Dar yerleşim eşiği; CSS'teki kırılma noktasıyla aynı olmalı (`_chart-extras.scss`). */
const COMPACT_WIDTH = 650;
const WIDE = { l: 58, r: 96, t: 18, b: 50 };
/** Dar ekranda y etiketleri çizim alanının içine alınır. */
const COMPACT = { l: 10, r: 74, t: 14, b: 46 };
const MAX_ZOOM = 6;
const YEAR_LABEL_SPAN = 200;
/** S1/R1 en önemli, S3/R3 (Camarilla'da S4/R4) en uzak; çizgi belirginliği buna göre kademelenir. */
const EMPHASIS: Record<string, string> = { P: 'pivot', R1: 'near', S1: 'near', R2: 'mid', S2: 'mid', R3: 'far', S3: 'far', R4: 'far', S4: 'far' };

type ChartProps = {
  forecast: Forecast;
  available: boolean;
  history: [string, number][];
  /** Sunucunun günlük mumları (h, l, c, pc); mum görünümü bunlardan çizilir. */
  candles: MarketCandle[];
  candleMode: boolean;
  rangeDays: number; horizonDays: number;
  /** Pivot kartıyla **aynı** merdiven; bant genişliği (`band`) de sunucudan gelir. */
  levels: LadderItem[];
  levelPeriod: string;
  /** Test edilmiş destek/direnç bölgeleri; güç yalnız saydamlık olarak okunur (betimleyici). */
  zones: Zone[];
  /** Dar ekranda çizilecek bölgelerin kimlikleri (sunucunun en yakın/test edilen seçimi). */
  focusZoneIds: string[];
  /** Tüm teknik blokların ölçtüğü referans fiyat ve çerçevesi; Harem kotasyonu değil. */
  reference: { value: number; frame: ReferenceFrame };
  describedById?: string;
};

type Point = { i: number; v: number; date: string; kind: string; lo?: number; hi?: number;
  /** Mum modunda gün içi yüksek/düşük; ipucu kartı bunları yazar. */
  dayHigh?: number; dayLow?: number };

function ForecastChart({
  forecast, available, history, candles, candleMode, rangeDays, horizonDays,
  levels, levelPeriod, zones, focusZoneIds, reference, describedById,
}: ChartProps) {
  const bandLabel = intervalLabel(forecast, resolveHorizon(forecast.horizons, horizonDays).index);
  const frameLabel = FRAME[reference.frame];
  const svgRef = useRef<SVGSVGElement | null>(null);
  /* Ölçüm SVG'de değil saran div'de: ResizeObserver <svg> için tetiklenmiyor. */
  const boxRef = useRef<HTMLDivElement | null>(null);
  /* Gün gezinme çubuğu SVG'nin dışında; sabitlemeyi bozmaması için sarmalayıcı. */
  const wrapRef = useRef<HTMLDivElement | null>(null);
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
  const [layers, setLayers] = useState({ history: true, live: true, model: true, band: true, levels: false, zones: false });
  const toggleLayer = (layer: keyof typeof layers) => {
    setLayers(current => ({ ...current, [layer]: !current[layer] }));
    setHover(null);
    setPinned(false);
  };

  /* Mumlar kapanış serisinden önce kurulur: ipucu kartı gün içi aralığı
     buradan okur ve `hist` ile aynı x indekslerini paylaşırlar. */
  const bars = useMemo(() => candleShapes(candles, rangeDays), [candles, rangeDays]);
  const barByDate = useMemo(() => new Map(bars.map(b => [b.date, b])), [bars]);

  const hist = useMemo<Point[]>(() => {
    const shown = history.slice(-rangeDays);
    return shown.map((d, i) => {
      const bar = barByDate.get(d[0]);
      return { i: i - (shown.length - 1), v: d[1], date: d[0], kind: 'Geçmiş',
        dayHigh: bar?.high, dayLow: bar?.low };
    });
  }, [history, rangeDays, barByDate]);
  const lastHistoryDate = hist.length ? hist[hist.length - 1].date : undefined;
  /* Mum satırı yoksa çizgiye düş; aksi hâlde mum modunda grafik bomboş kalır. */
  const showCandles = candleMode && bars.length > 0;

  /* Bölge katmanı: dar ekranda yalnız sunucunun işaret ettiği bölgeler
     (`focusZoneIds`), sunucunun gönderdiği sırada; geniş ekranda hepsi.
     Uzaklığa göre sıralayıp kesmek istemcide seviye seçimi olurdu. */
  const shownZones = useMemo(() => {
    if (!compact) return zones;
    const focus = new Set(focusZoneIds);
    return zones.filter(zone => focus.has(zone.id));
  }, [zones, focusZoneIds, compact]);
  const future = buildDailyPath(model, forecast, horizonDays, forecast.originDate ?? lastHistoryDate)
    .map(d => ({ ...d, i: d.day, kind: d.day === 0 ? 'Bugün' : `${d.day}. gün` }));

  const startI = -(hist.length - 1), endI = horizonDays;
  const visibleSpan = (endI - startI) / zoom;
  const center = Math.max(startI + visibleSpan / 2,
    Math.min(endI - visibleSpan / 2, (startI + endI) / 2 + panDays));
  const visibleStart = center - visibleSpan / 2, visibleEnd = center + visibleSpan / 2;

  const core = [
    ...hist.map(d => d.v), ...(available && (layers.model || layers.band) ? future.map(d => d.v) : []), reference.value,
    // Fitiller kapanış serisinin dışına taşar; ölçeğe katılmazsa kırpılırlardı.
    ...(layers.history && showCandles ? bars.flatMap(b => [b.wickHigh, b.wickLow]) : []),
  ];
  /* Pivot seviyeleri, bölgeler ve bant "kırpılabilir" kümede: S3/R3 fiyattan
     %10 uzakta olabiliyor, çekirdek kümeye konsa fiyat çizgisini düz bir hat yapardı. */
  const bandValues = [
    ...(available && layers.band ? future.flatMap(d => [d.lo, d.hi]) : []),
    ...(layers.levels ? levels.flatMap(l => l.band) : []),
    ...(layers.zones ? shownZones.flatMap(z => [z.low, z.high]) : []),
  ];
  const domain = computeDomain(core, bandValues);

  const x = (i: number) => m.l + (i - visibleStart) / (visibleEnd - visibleStart) * plotW;
  const y = (v: number) => m.t + (domain.max - v) / (domain.max - domain.min) * plotH;
  const inDomain = (v: number) => v >= domain.min && v <= domain.max;
  const line = (points: { i: number; v: number }[]) => points.map(d => `${x(d.i)},${y(d.v)}`).join(' ');
  const bandShape = `${future.map(d => `${x(d.i)},${y(d.hi)}`).join(' ')} `
    + `${[...future].reverse().map(d => `${x(d.i)},${y(d.lo)}`).join(' ')}`;

  const probePoints: Point[] = [
    ...(layers.history ? hist : []),
    ...(available && (layers.model || layers.band) ? future.slice(1) : []),
  ];
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
    svgRef, keepRef: wrapRef, zoomBy, panByPixels, probeAt,
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
    const current = hover ? probePoints.findIndex(p => p.i === hover.i && p.date === hover.date)
      : probePoints.findIndex(p => p.i === 0);
    const next = Math.max(0, Math.min(probePoints.length - 1, (current < 0 ? 0 : current) + delta));
    focusPoint(probePoints[next]);
  };
  const onKeyDown = (event: KeyboardEvent<SVGSVGElement>) => {
    if (!probePoints.length && event.key !== 'Escape') return;
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

  const last = future[future.length - 1];
  const summary = available
    ? `Solda son ${hist.length} günün gerçekleşen ons altın kapanışı, sağda ${horizonDays} günlük `
      + `model tahmini ve ${bandLabel}. Referans fiyat ${money(reference.value)} (${frameLabel}). `
      + `${horizonDays} gün sonrası için beklenti ${money(last.v)}, aralık ${money(last.lo)}–${money(last.hi)}. `
      + `${levelPeriod} pivot seviyeleri: ` + levels.map(l => `${l.name} ${money(l.value)}`).join(', ') + '.'
    : `Son ${hist.length} günün gerçekleşen ons altın kapanışı. Model tahmini bekleniyor.`;
  const spoken = !hover ? '' : Number.isFinite(hover.lo)
    ? `${longDate(hover.date)}: beklenti ${money(hover.v)}, aralık ${money(hover.lo!)}–${money(hover.hi!)}.`
    : `${longDate(hover.date)}: gerçekleşen ${money(hover.v)}.`;

  const tagW = compact ? 68 : 88;

  return <div className={`chart-wrap forecast-chart${pinned && hover ? ' has-selection' : ''}`} ref={wrapRef}>
    <div className="chart-legend chart-layer-controls" role="group" aria-label="Grafik katmanları">
      {([
        ['history', 'Fiyat', 'history-key', false, undefined],
        ['live', 'Referans', 'now-key', false, frameLabel],
        ['model', 'Model', 'forecast-key', !available, undefined],
        ['band', bandLabel, 'band-key', !available, undefined],
        ['levels', 'Destek / direnç', 'sr-key', levels.length === 0, undefined],
        ['zones', 'Bölgeler', 'sr-key', zones.length === 0, 'Test edilmiş bölgeler; saydamlık test yoğunluğunu gösterir'],
      ] as const).map(([key, label, icon, disabled, hint]) => <button type="button" key={key}
        className={layers[key] && !disabled ? 'on' : 'off'} aria-pressed={layers[key] && !disabled} disabled={disabled}
        title={disabled ? 'Bu katman için veri bekleniyor' : hint}
        onClick={() => toggleLayer(key)}>
        <i className={icon} aria-hidden="true"/><span>{label}</span>
        <span className="layer-state" aria-hidden="true">{layers[key] && !disabled ? '✓' : '+'}</span>
      </button>)}
    </div>
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
            {available && (layers.model || layers.band) && <rect className="future-zone" x={Math.max(m.l, x(0))} y={m.t}
                  width={Math.max(0, W - m.r - Math.max(m.l, x(0)))} height={plotH}/>}

            {/* Test edilmiş bölgeler: sunucunun gerçek [low, high] aralığı; saydamlık
                gücü (0-100) izler. Güç bir iddia değil test yoğunluğu, o yüzden
                yalnız ton olarak okunur ve başlıkta temas sayısı yazılır. */}
            {layers.zones && shownZones.map(zone => {
              if (zone.high < domain.min || zone.low > domain.max) return null;
              const kind = zone.kind === 'SUPPORT' ? 'sup' : 'res';
              const top = y(zone.high), bottom = y(zone.low);
              const tint = kind === 'sup' ? 'rgb(var(--teal-fill-rgb) / .45)' : 'rgb(var(--red-fill-rgb) / .45)';
              const caption = `${sourceLabel(zone.name)} · ${zone.touches} temas`;
              return <g key={zone.id} className={`sr-zone ${kind} zone`} opacity={zone.strength / 100}>
                <title>{caption}</title>
                <rect x={m.l} y={top} width={plotW} height={Math.max(2, bottom - top)} style={{ fill: tint }}/>
                <text className="sr-label" x={W - m.r - 8} y={bottom - 4} textAnchor="end">{caption}</text>
              </g>;
            })}

            {/* Pivot seviyeleri: pivot kartındakiyle birebir aynı sayılar ve aynı
                bant (`band`, sunucunun ATR marjı). S1/R1 belirgin, S3/R3 daha soluk. */}
            {layers.levels && levels.map(level => {
              if (!inDomain(level.value)) return null;
              /* Taraf sunucunun `above` kararı, ad öneki değil: Camarilla'da S1
                 pivotun üstünde kalabilir ve merdiven onu direnç satırı yapar. */
              const kind = level.name === 'P' ? 'pivot' : level.above ? 'res' : 'sup';
              const top = y(level.band[1]);
              const bottom = y(level.band[0]);
              return <g key={level.name} className={`sr-zone ${kind} ${EMPHASIS[level.name] ?? 'mid'}`}>
                <rect x={m.l} y={top} width={plotW} height={Math.max(3, bottom - top)}/>
                <line className="sr-mid" x1={m.l} y1={y(level.value)} x2={W - m.r} y2={y(level.value)}/>
                <text className="sr-label" x={m.l + 8} y={y(level.value) - 5}>
                  {level.name} · {money(level.value)}</text>
              </g>;
            })}

            {available && layers.band && <polygon className="band" points={bandShape}/>}
            {/* Mum görünümü: gövde sunucunun tanımıyla önceki kapanış → kapanış,
                fitil gün içi yüksek/düşük. Şekil `./geometry.ts` içinde kurulur. */}
            {layers.history && (showCandles ? (() => {
              const w = candleWidth(plotW / (visibleEnd - visibleStart));
              return <g className="candles">{bars.map(b => {
                if (b.i < visibleStart - 1 || b.i > visibleEnd + 1) return null;
                const cx = x(b.i);
                const top = y(b.bodyTop);
                const bottom = y(b.bodyBottom);
                return <g key={b.date} className={`candle ${b.up ? 'up' : 'down'}`}>
                  <line className="candle-wick" x1={cx} y1={y(b.wickHigh)} x2={cx} y2={y(b.wickLow)}/>
                  <rect className="candle-body" x={cx - w / 2} y={top}
                    width={w} height={Math.max(1, bottom - top)}/>
                </g>;
              })}</g>;
            })() : <polyline className="history" points={line(hist)}/>)}
            {available && layers.model && <polyline className="forecast" points={line(future)}/>}
            {/* Referans fiyat çizgisi: tüm seviyelerin ölçüldüğü fiyat (GC=F
                kapanışı), Harem kotasyonu değil — aynı merdiven iki çerçevede
                farklı "en yakın seviye" veriyordu. Çizgi grafiği sağdaki etikete
                bağlar; mum modunda çizgi gizliyken de referans okunur. */}
            {layers.live && <g className="live-price-layer">
            <line className="now-line" x1={m.l} y1={y(reference.value)} x2={W - m.r} y2={y(reference.value)}/>
            {/* Destek çizgileri de yeşil; referans kendi etiketiyle ayrışsın.
                Etiket, S/R çizgilerindeki adlandırma düzeniyle aynı yerde durur. */}
            <text className="now-line-label" x={m.l + 8} y={y(reference.value) + 12}>
              <title>{frameLabel}</title>REFERANS</text>
            <circle className="now-dot-ons" cx={x(0)} cy={y(reference.value)} r="5"/>
            </g>}
          </g>

          <line className="today-divider" x1={x(0)} y1={m.t} x2={x(0)} y2={H - m.b}/>
          <text className="today-caption" x={x(0)} y={m.t - 4} textAnchor="middle">bugün</text>

          {layers.live && <g transform={`translate(${W - m.r + 4} ${Math.min(H - m.b - 24, Math.max(m.t, y(reference.value) - 12))})`}>
            <title>{frameLabel}</title>
            <rect className="now-card" width={tagW} height="24" rx="4"/>
            <text className="now-value" x={tagW / 2} y="16" textAnchor="middle">{money(reference.value)}</text>
          </g>}

          {timeTicks.map(i => {
            const date = dateByIndex.get(i);
            return date && <text key={i} className="axis time"
                  x={Math.min(W - m.r, Math.max(m.l, x(i)))} y={H - m.b + 18} textAnchor="middle">
              {shortDate(date, withYear)}</text>;
          })}
          <text className="axis time anchor" x={x(0)} y={H - m.b + 18} textAnchor="middle">bugün</text>

          {hover && (() => {
            const isForecast = Number.isFinite(hover.lo) && Number.isFinite(hover.hi);
            /* Mum modunda gün içi aralık satırı eklenir; kart o kadar uzar. */
            const showRange = !isForecast && showCandles
              && Number.isFinite(hover.dayHigh) && Number.isFinite(hover.dayLow);
            const shift = showRange ? 21 : 0;
            const boxW = isForecast ? (compact ? 200 : 224) : showRange ? (compact ? 190 : 214) : (compact ? 146 : 166);
            const boxH = (isForecast ? 92 : 48) + (isForecast ? 0 : shift);
            const cornerX = x(hover.i) < W / 2 ? W - m.r - boxW - 6 : m.l + 6;
            const boxX = pinned ? cornerX : Math.min(W - m.r - boxW - 6, Math.max(m.l + 5, x(hover.i) + 12));
            const boxY = pinned ? m.t + 6 : Math.min(H - m.b - boxH - 6, Math.max(10, y(hover.v) - boxH / 2));
            return <g className="crosshair">
              <line x1={x(hover.i)} y1={m.t} x2={x(hover.i)} y2={H - m.b}/>
              {isForecast && layers.band && <>
                <line className="band-range" x1={x(hover.i)} y1={y(hover.hi!)} x2={x(hover.i)} y2={y(hover.lo!)}/>
                <circle className="band-max-dot" cx={x(hover.i)} cy={y(hover.hi!)} r="4"/>
                <circle className="band-min-dot" cx={x(hover.i)} cy={y(hover.lo!)} r="4"/>
              </>}
              <circle cx={x(hover.i)} cy={y(hover.v)} r="6"/>
              <g className="time-badge" transform={`translate(${x(hover.i)} ${H - m.b + 6})`}>
                <rect x="-31" y="0" width="62" height="18" rx="5"/>
                <text y="13" textAnchor="middle">{shortDate(hover.date, withYear)}</text>
              </g>
              <g className="hover-card" transform={`translate(${boxX} ${boxY})`}>
                <rect width={boxW} height={boxH} rx="8"/>
                <text x="11" y="19">{longDate(hover.date)}</text>
                {isForecast ? <>
                  <text x="11" y="40" className="tip-min">Alt bant</text>
                  <text x={boxW - 11} y="40" textAnchor="end" className="tip-value tip-min">{money(hover.lo!)}</text>
                  <text x="11" y="61" className="tip-price">Beklenen</text>
                  <text x={boxW - 11} y="61" textAnchor="end" className="tip-value tip-price">{money(hover.v)}</text>
                  <text x="11" y="82" className="tip-max">Üst bant</text>
                  <text x={boxW - 11} y="82" textAnchor="end" className="tip-value tip-max">{money(hover.hi!)}</text>
                </> : <>
                  <text x="11" y="40" className="tip-real">Gerçekleşen</text>
                  <text x={boxW - 11} y="40" textAnchor="end" className="tip-value tip-real">{money(hover.v)}</text>
                  {showRange && <>
                    <text x="11" y="61" className="tip-min">Gün içi aralık</text>
                    <text x={boxW - 11} y="61" textAnchor="end" className="tip-value tip-min">
                      {money(hover.dayLow!)} – {money(hover.dayHigh!)}</text>
                  </>}
                </>}
              </g>
            </g>;
          })()}
        </>}
      </svg>
    </div>

    {pinned && hover && compact && <div className="chart-probe">
      <div className="chart-probe-title"><span>{longDate(hover.date)}</span>
        <b>{Number.isFinite(hover.lo) ? 'Model beklentisi' : 'Gerçekleşen kapanış'}</b></div>
      <strong>{money(hover.v)}</strong>
      {Number.isFinite(hover.lo) && <p>{bandLabel}: {money(hover.lo!)} – {money(hover.hi!)}</p>}
      {showCandles && Number.isFinite(hover.dayLow) && <p>
        Gün içi: {money(hover.dayLow!)} – {money(hover.dayHigh!)}</p>}
    </div>}

    {/* Gün gün gezinme: parmakla sürüklemek kabaca yaklaştırır, bu düğmeler
        tam güne oturtur. Klavye okları da aynı `step`'i kullanır. */}
    {pinned && hover && <div className="day-stepper">
      <button type="button" onClick={() => step(-1)} aria-label="Önceki gün">‹</button>
      <b>{longDate(hover.date)}</b>
      <button type="button" onClick={() => step(1)} aria-label="Sonraki gün">›</button>
      <button type="button" className="day-stepper-close"
        onClick={() => { setHover(null); setPinned(false); }}>Kapat</button>
    </div>}

    <p className="sr-live" role="status" aria-live="polite">{spoken}</p>
    <p className="chart-hint">
      {compact ? 'Parmağını grafikte gezdir · iki parmakla kaydır ve yakınlaştır'
               : 'Sürükleyerek kaydır · tekerlekle yakınlaştır · üzerine gelince o günün değerleri görünür'}
    </p>
  </div>;
}

export default ForecastChart;
