import { describe, expect, it } from 'vitest';
import { buildLadder, computePivots, type PivotSet } from './pivots';
import type { Candle } from './indicators';

const bar = (date: string, h: number, l: number, c: number): Candle => ({ date, h, l, c });

/** İki tam ay + içinde bulunulan ay: son tamamlanan ay Şubat olmalı. */
const series: Candle[] = [
  ...Array.from({ length: 20 }, (_, i) => bar(`2026-01-${String(i + 1).padStart(2, '0')}`, 110, 90, 100)),
  ...Array.from({ length: 20 }, (_, i) => bar(`2026-02-${String(i + 1).padStart(2, '0')}`, 130, 70, 120)),
  ...Array.from({ length: 5 }, (_, i) => bar(`2026-03-${String(i + 1).padStart(2, '0')}`, 200, 60, 150)),
];

describe('computePivots', () => {
  it('yetersiz mumda null döner', () => {
    expect(computePivots(series.slice(0, 39))).toBeNull();
  });

  it('içinde bulunulan dönemi atlayıp son tamamlanan dönemi kullanır', () => {
    const p = computePivots(series)!;
    expect(p.monthly!.id).toBe('2026-02');   // Mart devam ediyor, sayılmaz
  });

  it('klasik pivot formülünü doğru uygular', () => {
    const p = computePivots(series)!.monthly!;
    const [h, l, c] = [130, 70, 120];
    const pivot = (h + l + c) / 3;
    expect(p.pivot).toBeCloseTo(pivot, 10);
    expect(p.classic.r1).toBeCloseTo(2 * pivot - l, 10);
    expect(p.classic.s1).toBeCloseTo(2 * pivot - h, 10);
    expect(p.classic.r2).toBeCloseTo(pivot + (h - l), 10);
    expect(p.classic.s2).toBeCloseTo(pivot - (h - l), 10);
  });

  it('Fibonacci seviyeleri aralığın 0,382 / 0,618 / 1,0 katıdır', () => {
    const p = computePivots(series)!.monthly!;
    const range = 130 - 70;
    expect(p.fib.r1 - p.pivot).toBeCloseTo(0.382 * range, 10);
    expect(p.pivot - p.fib.s2).toBeCloseTo(0.618 * range, 10);
    expect(p.fib.r3 - p.pivot).toBeCloseTo(range, 10);
  });
});

const set: PivotSet = {
  id: '2026-02', pivot: 100,
  classic: { r3: 130, r2: 120, r1: 110, s1: 90, s2: 80, s3: 70 },
  fib: { r3: 130, r2: 120, r1: 110, s1: 90, s2: 80, s3: 70 },
};

describe('buildLadder', () => {
  it('seviyeleri büyükten küçüğe sıralar', () => {
    const l = buildLadder(set, 'classic', 100)!;
    expect(l.items.map(i => i.name)).toEqual(['R3', 'R2', 'R1', 'P', 'S1', 'S2', 'S3']);
  });

  it('fiyat aralığın ortasındayken doğru yere yerleşir', () => {
    const l = buildLadder(set, 'classic', 105)!;
    // insertAt = işaretçinin ÖNÜNE geleceği satır; 105, R1 (110) ile P (100) arasında
    expect(l.items[l.insertAt].name).toBe('P');
    expect(l.nearestUp).toBe('R1');
    expect(l.nearestDown).toBe('P');
  });

  it('fiyat tüm seviyelerin üstündeyse en başa yerleşir', () => {
    // Aylık pivot geride kaldığında fiyat hepsinin üstünde kalıyor ve
    // "şu an" satırı hiç görünmüyordu; bu test o regresyonu kilitler.
    const l = buildLadder(set, 'classic', 500)!;
    expect(l.insertAt).toBe(0);
    expect(l.nearestUp).toBeUndefined();
    expect(l.nearestDown).toBe('R3');
  });

  it('fiyat tüm seviyelerin altındaysa en sona yerleşir', () => {
    const l = buildLadder(set, 'classic', 10)!;
    expect(l.insertAt).toBe(l.items.length);
    expect(l.nearestUp).toBe('S3');
  });

  it('uzaklık yüzdesi fiyata göre hesaplanır', () => {
    const l = buildLadder(set, 'classic', 100)!;
    expect(l.items.find(i => i.name === 'R2')!.distance).toBeCloseTo(0.2, 10);
  });
});
