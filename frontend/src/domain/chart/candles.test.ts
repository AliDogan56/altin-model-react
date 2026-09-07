import { describe, expect, it } from 'vitest';
import type { Candle } from '../indicators';
import { buildCandles, candleWidth } from './candles';

const bar = (date: string, h: number, l: number, c: number): Candle => ({ date, h, l, c });

const series: Candle[] = [
  bar('2026-08-17', 4500, 4440, 4480),
  bar('2026-08-18', 4530, 4470, 4520),   // yükseliş: 4480 -> 4520
  bar('2026-08-19', 4525, 4450, 4460),   // düşüş:    4520 -> 4460
  bar('2026-08-20', 4600, 4455, 4590),
  bar('2026-08-21', 4624, 4560, 4600),
];

describe('buildCandles', () => {
  it('gövdeyi önceki kapanıştan bugünkü kapanışa kurar', () => {
    // Kaynakta açılış yok; gövde günün net hareketini gösterir.
    const out = buildCandles(series, 3);
    expect(out.map(c => c.date)).toEqual(['2026-08-19', '2026-08-20', '2026-08-21']);
    expect(out[0]).toMatchObject({ open: 4520, close: 4460, up: false });
    expect(out[1]).toMatchObject({ open: 4460, close: 4590, up: true });
  });

  it('son mumun indeksi 0, geçmiş negatif', () => {
    expect(buildCandles(series, 3).map(c => c.i)).toEqual([-2, -1, 0]);
  });

  it('istenen aralık için bir gün fazlasını okur', () => {
    // 3 mum isteniyorsa ilk mumun gövdesi 4. günün kapanışına ihtiyaç duyar.
    const out = buildCandles(series, 3);
    expect(out).toHaveLength(3);
    expect(out[0].open).toBe(4520);          // 2026-08-18 kapanışı
  });

  it('serinin en başında önceki gün yoksa gövde sıfır yükseklikte kalır', () => {
    const out = buildCandles(series, 99);
    expect(out).toHaveLength(series.length);
    expect(out[0]).toMatchObject({ open: 4480, close: 4480, up: true });
  });

  it('kapanış gün aralığının dışındaysa fitili genişletir', () => {
    // Kaynak nadiren tutarsız veriyor; gövde fitilin dışına taşmamalı.
    const odd: Candle[] = [bar('2026-08-20', 4500, 4400, 4450), bar('2026-08-21', 4480, 4460, 4520)];
    const [, today] = buildCandles(odd, 2);
    expect(today.high).toBe(4520);           // kapanış yüksekten büyük
    expect(today.low).toBe(4450);            // önceki kapanış düşükten küçük
  });

  it('boş seri ve sıfır aralık güvenli', () => {
    expect(buildCandles([], 30)).toEqual([]);
    expect(buildCandles(series, 0)).toEqual([]);
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
