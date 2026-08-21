import type { Candle } from './indicators';

export type PivotLevels = { r3: number; r2: number; r1: number; s1: number; s2: number; s3: number };
export type PivotSet = { id: string; pivot: number; classic: PivotLevels; fib: PivotLevels };
export type Pivots = { weekly: PivotSet | null; monthly: PivotSet | null };

const isoWeek = (date: string): string => {
  const d = new Date(`${date}T00:00:00Z`);
  const day = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - day);
  return d.toISOString().slice(0, 10);
};

/** Son *tamamlanan* dönemin yüksek/düşük/kapanışı; içinde bulunulan dönem atlanır. */
const lastCompletePeriod = (candles: Candle[], key: (date: string) => string) => {
  const groups = new Map<string, { h: number; l: number; c: number }>();
  candles.forEach(candle => {
    const id = key(candle.date);
    const g = groups.get(id);
    if (!g) groups.set(id, { h: candle.h, l: candle.l, c: candle.c });
    else { g.h = Math.max(g.h, candle.h); g.l = Math.min(g.l, candle.l); g.c = candle.c; }
  });
  const ids = [...groups.keys()].sort();
  return ids.length < 2 ? null : { id: ids[ids.length - 2], ...groups.get(ids[ids.length - 2])! };
};

const levelsOf = (bar: { h: number; l: number; c: number }) => {
  const p = (bar.h + bar.l + bar.c) / 3;
  const range = bar.h - bar.l;
  return {
    pivot: p,
    classic: { r3: bar.h + 2 * (p - bar.l), r2: p + range, r1: 2 * p - bar.l, s1: 2 * p - bar.h, s2: p - range, s3: bar.l - 2 * (bar.h - p) },
    fib: { r3: p + range, r2: p + 0.618 * range, r1: p + 0.382 * range, s1: p - 0.382 * range, s2: p - 0.618 * range, s3: p - range },
  };
};

/**
 * Pivot seviyeleri önceki tam dönemden türetilir. Kendi bulduğumuz destek/direnç
 * kümelerinden farklı olarak deterministiktir; ikisi çakışırsa seviye güçlü demektir.
 * Günlük pivot 90-180 günlük grafikte çok dar kaldığı için haftalık ve aylık kullanılır.
 */
export const computePivots = (candles: Candle[]): Pivots | null => {
  if (candles.length < 40) return null;
  const weekly = lastCompletePeriod(candles, isoWeek);
  const monthly = lastCompletePeriod(candles, date => date.slice(0, 7));
  return {
    weekly: weekly && { ...levelsOf(weekly), id: weekly.id },
    monthly: monthly && { ...levelsOf(monthly), id: monthly.id },
  };
};

export type LadderItem = { name: string; value: number; distance: number; above: boolean };
export type Ladder = { id: string; price: number; items: LadderItem[]; insertAt: number; nearestUp?: string; nearestDown?: string };

/** Seviyeler fiyata göre sıralanır; canlı fiyat aralarındaki yerine yerleşir. */
export const buildLadder = (set: PivotSet | null, method: 'classic' | 'fib', price: number): Ladder | null => {
  if (!set) return null;
  const rows = method === 'classic' ? set.classic : set.fib;
  const items = ([['R3', rows.r3], ['R2', rows.r2], ['R1', rows.r1], ['P', set.pivot],
    ['S1', rows.s1], ['S2', rows.s2], ['S3', rows.s3]] as [string, number][])
    .map(([name, value]) => ({ name, value, distance: price ? value / price - 1 : 0, above: value >= price }))
    .sort((a, b) => b.value - a.value);
  const below = items.findIndex(i => !i.above);
  return {
    id: set.id, price, items,
    insertAt: below < 0 ? items.length : below,   // fiyat hepsinin üstündeyse en başa, altındaysa en sona
    nearestUp: items.filter(i => i.above).at(-1)?.name,
    nearestDown: items.find(i => !i.above)?.name,
  };
};
