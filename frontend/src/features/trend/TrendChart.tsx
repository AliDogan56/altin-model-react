import { useId, useRef } from 'react';
import { candleWidth } from '../chart/geometry';
import { DIRECTION, type Timeframe } from '../../content/trend';
import { useElementSize } from '../chart/useElementSize';
import { money } from '../../lib/format';
import type { TrendFit, TrendRow } from '../../services/api/technical';

const COMPACT_WIDTH = 650;
const WIDE = { l: 58, r: 18, t: 18, b: 42 };
const COMPACT = { l: 10, r: 12, t: 14, b: 40 };
const TICKS = 5;

const kisaTarih = (iso: string, timeframe: Timeframe) => {
  const [y, m, d] = iso.split('-');
  return timeframe === 'DAILY' || timeframe === 'WEEKLY' ? `${d}.${m}` : `${m}.${y.slice(2)}`;
};

/**
 * Trend grafiği. Her sayı sunucudan hazır gelir: mum gövdesi `prevClose → close`,
 * fitil `wickLow..wickHigh` (kapanışları da kapsayacak şekilde sunucuda
 * genişletilmiş), trend değeri `row.fit`, kanal `row.b1/b2`. Burada yalnız
 * piksel eşlemesi ve y ekseni aralığı hesaplanır — saf geometri.
 *
 * Ölçüm SVG'de değil saran div'de yapılır — ResizeObserver `<svg>` için
 * tetiklenmiyor; bu, mevcut grafikte ölçülmüş bir tuzak.
 */
function TrendChart({ rows, fit, candles, timeframe, label }: {
  rows: TrendRow[]; fit: TrendFit | null; candles: boolean; timeframe: Timeframe; label: string;
}) {
  const boxRef = useRef<HTMLDivElement | null>(null);
  const clipId = useId();
  const hatchId = useId();
  const { width: W, height: H } = useElementSize(boxRef);
  const ready = W > 60 && H > 60 && rows.length > 1;
  const compact = W < COMPACT_WIDTH;
  const m = compact ? COMPACT : WIDE;
  const plotW = Math.max(1, W - m.l - m.r);
  const plotH = Math.max(1, H - m.t - m.b);

  /* Ölçek: mum modunda fitiller, her modda trend değeri ve 2σ bandı kapsanır;
     yoksa uçları kırpılır. Bant çarpımsal olduğu için satır satır bakılır. */
  const degerler = rows.flatMap(r => [
    ...(candles ? [r.wickHigh, r.wickLow] : [r.close]),
    ...(r.fit === null ? [] : [r.fit]),
    ...(r.b2 ?? []),
  ]);
  const ham = { min: Math.min(...degerler), max: Math.max(...degerler) };
  const pay = (ham.max - ham.min) * 0.08 || Math.max(1, ham.max * 0.01);
  const min = ham.min - pay, max = ham.max + pay;

  const x = (i: number) => m.l + (rows.length === 1 ? plotW / 2 : (i / (rows.length - 1)) * plotW);
  const y = (v: number) => m.t + (max - v) / (max - min || 1) * plotH;
  const pt = (i: number, v: number) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`;

  const cizgi = rows.map((r, i) => pt(i, r.close)).join(' ');
  const fitCizgi = rows.flatMap((r, i) => r.fit === null ? [] : [pt(i, r.fit)]).join(' ');
  const tone = fit ? DIRECTION[fit.direction].tone : 'flat';
  const hasBand = rows.some(r => r.b1 !== null);
  /* Kanal poligonu: üst kenar ileri, alt kenar geri; bandı olmayan satır atlanır. */
  const bant = (k: 1 | 2) => {
    const sec = (r: TrendRow) => (k === 1 ? r.b1 : r.b2);
    const ust = rows.flatMap((r, i) => { const b = sec(r); return b ? [pt(i, b[1])] : []; });
    const alt = rows.flatMap((r, i) => { const b = sec(r); return b ? [pt(i, b[0])] : []; }).reverse();
    return [...ust, ...alt].join(' ');
  };
  const adim = Math.max(1, Math.ceil(rows.length / (compact ? 4 : 7)));
  const son = rows[rows.length - 1];
  const w = candleWidth(plotW / Math.max(1, rows.length));

  return <div className="chart-wrap trend-wrap" ref={boxRef}>
    <svg className={`chart ${compact ? 'compact' : ''}`} viewBox={`0 0 ${W} ${H}`}
      role="img" aria-label={`${label} ons altın seyri ve trend çizgisi`}>
      {ready && <>
        <defs>
          <clipPath id={clipId}><rect x={m.l} y={m.t} width={plotW} height={plotH}/></clipPath>
          {/* Oluşan (kapanmamış) dönemin gövdesi tarama ile dolar: sayı henüz
              kesinleşmedi, dolu mumla aynı görünmesin. */}
          <pattern id={hatchId} width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="4" className="trend-hatch"/>
          </pattern>
        </defs>

        {Array.from({ length: TICKS }, (_, k) => {
          const v = min + (max - min) * k / (TICKS - 1);
          return <g key={k}>
            <line className="gridline" x1={m.l} y1={y(v)} x2={W - m.r} y2={y(v)}/>
            {compact
              ? <text className="axis inside" x={m.l + 4} y={y(v) - 4}>{Math.round(v).toLocaleString('tr-TR')}</text>
              : <text className="axis" x={m.l - 8} y={y(v) + 3} textAnchor="end">{Math.round(v).toLocaleString('tr-TR')}</text>}
          </g>;
        })}

        <g clipPath={`url(#${clipId})`}>
          {/* Regresyon kanalı: sunucunun ±1σ ve ±2σ bandı. Log uzayında simetrik,
              fiyat ekseninde çarpımsal açılır. İleriye dönük bir iddia değil;
              uyum oranını (r²) görünür kılar. */}
          {hasBand && [2, 1].map(k => (
            <polygon key={k} className={`trend-band k${k}`} points={bant(k as 1 | 2)}/>
          ))}

          {candles
            ? <g className="candles">{rows.map((r, i) => {
                /* Önceki kapanış yoksa (serinin ilk mumu) gövde sıfır yükseklikte kalır. */
                const onceki = r.prevClose ?? r.close;
                const up = r.close >= onceki;
                const top = y(Math.max(onceki, r.close));
                const bottom = y(Math.min(onceki, r.close));
                return <g key={r.date} className={`candle ${up ? 'up' : 'down'}${r.complete ? '' : ' forming'}`}>
                  {!r.complete && <title>oluşan dönem</title>}
                  <line className="candle-wick" x1={x(i)} y1={y(r.wickHigh)} x2={x(i)} y2={y(r.wickLow)}/>
                  <rect className="candle-body" x={x(i) - w / 2} y={top}
                    width={w} height={Math.max(1, bottom - top)}
                    style={r.complete ? undefined : { fill: `url(#${hatchId})` }}/>
                </g>;
              })}</g>
            : <polyline className="history" points={cizgi}/>}

          {/* Genel yön: sunucunun satır başına trend değeri; noktaları birleştirmez. */}
          {fitCizgi && <polyline className={`trend-line ${tone}`} points={fitCizgi}/>}

          {/* Çizgi modunda oluşan dönem, son noktada içi boş bir işaretle ayrılır. */}
          {!candles && !son.complete &&
            <circle className="forming-point" cx={x(rows.length - 1)} cy={y(son.close)} r={4}>
              <title>oluşan dönem</title></circle>}
        </g>

        {rows.map((r, i) => i % adim === 0 || i === rows.length - 1 ? (
          <text key={r.date} className="axis time" x={x(i)} y={H - m.b + 18} textAnchor="middle">
            {kisaTarih(r.date, timeframe)}
          </text>) : null)}

        {fit && <text className="trend-endpoint" x={x(rows.length - 1) - 6}
          y={y(fit.last) - 8} textAnchor="end">{money(fit.last)}</text>}
      </>}
    </svg>
  </div>;
}

export default TrendChart;
