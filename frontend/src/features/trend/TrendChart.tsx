import { useId, useRef } from 'react';
import type { Candle } from '../../domain/indicators';
import { candleWidth } from '../../domain/chart/candles';
import type { Trend } from '../../domain/chart/trend';
import { useElementSize } from '../chart/useElementSize';
import { money } from '../../lib/format';
import type { RangeSpec } from './ranges';

const COMPACT_WIDTH = 650;
const WIDE = { l: 58, r: 18, t: 18, b: 42 };
const COMPACT = { l: 10, r: 12, t: 14, b: 40 };
const TICKS = 5;

const kisaTarih = (iso: string, bucket: string) => {
  const [y, m, d] = iso.split('-');
  if (bucket === 'gun' || bucket === 'hafta') return `${d}.${m}`;
  if (bucket === 'ay') return `${m}.${y.slice(2)}`;
  return `${m}.${y.slice(2)}`;
};

/**
 * Trend grafiği. Mevcut tahmin grafiğiyle aynı tasarım dilini kullanır
 * (aynı ızgara, eksen, mum ve efsane sınıfları) ama tahmin, bant ve hareket
 * mantığı yoktur: tek işi seçilen aralığın seyrini ve genel yönünü göstermek.
 *
 * Ölçüm SVG'de değil saran div'de yapılır — ResizeObserver `<svg>` için
 * tetiklenmiyor; bu, mevcut grafikte ölçülmüş bir tuzak.
 */
function TrendChart({ rows, trend, spec }: {
  rows: Candle[]; trend: Trend | null; spec: RangeSpec;
}) {
  const boxRef = useRef<HTMLDivElement | null>(null);
  const clipId = useId();
  const { width: W, height: H } = useElementSize(boxRef);
  const ready = W > 60 && H > 60 && rows.length > 1;
  const compact = W < COMPACT_WIDTH;
  const m = compact ? COMPACT : WIDE;
  const plotW = Math.max(1, W - m.l - m.r);
  const plotH = Math.max(1, H - m.t - m.b);

  /* Ölçek: mum modunda fitiller de kapsanmalı, yoksa uçları kırpılır.
     Trend çizgisi de kapsanır ki grafik dışına taşmasın. */
  const degerler = rows.flatMap(r => spec.candles ? [r.h, r.l] : [r.c]);
  if (trend) {
    degerler.push(trend.first, trend.last);
    /* Kanalın uçları da ölçeğe girer, yoksa 2σ bandı grafiğin dışında kalır.
       Bant çarpımsal olduğu için en geniş yeri son noktadır. */
    [0, rows.length - 1].forEach(i => degerler.push(trend.band(i, 2), trend.band(i, -2)));
  }
  const ham = { min: Math.min(...degerler), max: Math.max(...degerler) };
  const pay = (ham.max - ham.min) * 0.08 || Math.max(1, ham.max * 0.01);
  const min = ham.min - pay, max = ham.max + pay;

  const x = (i: number) => m.l + (rows.length === 1 ? plotW / 2 : (i / (rows.length - 1)) * plotW);
  const y = (v: number) => m.t + (max - v) / (max - min || 1) * plotH;

  const cizgi = rows.map((r, i) => `${x(i).toFixed(1)},${y(r.c).toFixed(1)}`).join(' ');
  const adim = Math.max(1, Math.ceil(rows.length / (compact ? 4 : 7)));

  return <div className="chart-wrap trend-wrap" ref={boxRef}>
    <svg className={`chart ${compact ? 'compact' : ''}`} viewBox={`0 0 ${W} ${H}`}
      role="img" aria-label={`${spec.label} ons altın seyri ve trend çizgisi`}>
      {ready && <>
        <defs><clipPath id={clipId}>
          <rect x={m.l} y={m.t} width={plotW} height={plotH}/></clipPath></defs>

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
          {/* Regresyon kanalı: artıkların ±1σ ve ±2σ bandı. Bant log uzayında
              simetrik, fiyat ekseninde çarpımsal açılır — %8'lik sapma yüksek
              fiyatta daha çok dolar eder. İleriye dönük bir iddia değil;
              uyum oranını (r²) görünür kılar. */}
          {trend && trend.sigma > 0 && [2, 1].map(k => (
            <polygon key={k} className={`trend-band k${k}`} points={[
              ...rows.map((_, i) => `${x(i).toFixed(1)},${y(trend.band(i, k)).toFixed(1)}`),
              ...rows.map((_, i) => i).reverse()
                .map(i => `${x(i).toFixed(1)},${y(trend.band(i, -k)).toFixed(1)}`),
            ].join(' ')}/>
          ))}

          {spec.candles ? (() => {
            const w = candleWidth(plotW / Math.max(1, rows.length));
            return <g className="candles">{rows.map((r, i) => {
              const onceki = i > 0 ? rows[i - 1].c : r.c;
              const up = r.c >= onceki;
              const top = y(Math.max(onceki, r.c));
              const bottom = y(Math.min(onceki, r.c));
              return <g key={r.date} className={`candle ${up ? 'up' : 'down'}`}>
                <line className="candle-wick" x1={x(i)} y1={y(r.h)} x2={x(i)} y2={y(r.l)}/>
                <rect className="candle-body" x={x(i) - w / 2} y={top}
                  width={w} height={Math.max(1, bottom - top)}/>
              </g>;
            })}</g>;
          })() : <polyline className="history" points={cizgi}/>}

          {/* Genel yön: regresyondan gelen düz çizgi, noktaları birleştirmez. */}
          {trend && <line className={`trend-line ${trend.direction}`}
            x1={x(0)} y1={y(trend.first)}
            x2={x(rows.length - 1)} y2={y(trend.last)}/>}
        </g>

        {rows.map((r, i) => i % adim === 0 || i === rows.length - 1 ? (
          <text key={r.date} className="axis time" x={x(i)} y={H - m.b + 18} textAnchor="middle">
            {kisaTarih(r.date, spec.bucket)}
          </text>) : null)}

        {trend && <text className="trend-endpoint" x={x(rows.length - 1) - 6}
          y={y(trend.last) - 8} textAnchor="end">{money(trend.last)}</text>}
      </>}
    </svg>
  </div>;
}

export default TrendChart;
