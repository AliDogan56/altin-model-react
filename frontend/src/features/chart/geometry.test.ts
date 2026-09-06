import { describe, expect, it } from 'vitest';
import type { MarketCandle } from '../dashboard/useTechnical';
import { candleShapes, candleWidth } from './geometry';

const bar = (date: string, h: number, l: number, c: number, pc: number | null): MarketCandle => ({ date, h, l, c, pc });

/* `pc` sunucudan gelir (`prev_close_to_close`); burada yalnız çizime dökülür. */
const series: MarketCandle[] = [
  bar('2026-08-17', 4500, 4440, 4480, null),
  bar('2026-08-18', 4530, 4470, 4520, 4480),
  bar('2026-08-19', 4525, 4450, 4460, 4520),
  bar('2026-08-20', 4600, 4455, 4590, 4460),
  bar('2026-08-21', 4624, 4560, 4600, 4590),
];

describe('candleShapes', () => {
  it('gövde uçlarını sunucunun pc/c çiftinden alır, hangisi üstteyse', () => {
    const out = candleShapes(series, 3);
    expect(out.map(c => c.date)).toEqual(['2026-08-19', '2026-08-20', '2026-08-21']);
    expect(out[0]).toMatchObject({ bodyTop: 4520, bodyBottom: 4460, up: false });
    expect(out[1]).toMatchObject({ bodyTop: 4590, bodyBottom: 4460, up: true });
  });

  it('son mumun indeksi 0, geçmiş negatif', () => {
    expect(candleShapes(series, 3).map(c => c.i)).toEqual([-2, -1, 0]);
  });

  it('pc yoksa gövde kapanışta sıfır yükseklikte kalır', () => {
    const [first] = candleShapes(series, 99);
    expect(first).toMatchObject({ bodyTop: 4480, bodyBottom: 4480, up: true });
  });

  it('fitil gövdeyi kapsar; kapanış gün aralığı dışındaysa genişler', () => {
    const odd = [bar('2026-08-21', 4480, 4460, 4520, 4450)];
    const [today] = candleShapes(odd, 1);
    expect(today.wickHigh).toBe(4520);   // kapanış yüksekten büyük
    expect(today.wickLow).toBe(4450);    // önceki kapanış düşükten küçük
    expect(today).toMatchObject({ high: 4480, low: 4460 }); // ölçülen aralık değişmez
  });

  it('boş seri ve sıfır aralık güvenli', () => {
    expect(candleShapes([], 30)).toEqual([]);
    expect(candleShapes(series, 0)).toEqual([]);
  });
});

describe('candleWidth', () => {
  it('gün başına piksele göre ölçeklenir', () => {
    expect(candleWidth(10)).toBeCloseTo(6.8);
  });

  it('okunurluk için alt ve üst sınırla kırpılır', () => {
    expect(candleWidth(0.2)).toBe(1);        // bir yıllık aralıkta bile çizilir
    expect(candleWidth(400)).toBe(14);       // tek gün ekranı doldurmasın
  });
});
