import { describe, expect, it } from 'vitest';
import { buildLadder, computePivots, type PivotSet } from './pivots';
import type { Candle } from './indicators';

const bar = (date: string, h: number, l: number, c: number): Candle => ({ date, h, l, c });

/** Ölçümün sabit kalması için "bugün" her çağrıda açıkça verilir. */
const TODAY = '2026-03-06';

/** İki tam ay + içinde bulunulan ay: son tamamlanan ay Şubat olmalı. */
const series: Candle[] = [
  ...Array.from({ length: 20 }, (_, i) => bar(`2026-01-${String(i + 1).padStart(2, '0')}`, 110, 90, 100)),
  ...Array.from({ length: 20 }, (_, i) => bar(`2026-02-${String(i + 1).padStart(2, '0')}`, 130, 70, 120)),
  ...Array.from({ length: 5 }, (_, i) => bar(`2026-03-${String(i + 1).padStart(2, '0')}`, 200, 60, 150)),
];

describe('computePivots', () => {
  it('yetersiz mumda null döner', () => {
    expect(computePivots(series.slice(0, 39), TODAY)).toBeNull();
  });

  it('içinde bulunulan dönemi atlayıp son tamamlanan dönemi kullanır', () => {
    const p = computePivots(series, TODAY)!;
    expect(p.monthly!.id).toBe('2026-02');   // Mart devam ediyor, sayılmaz
  });

  it('klasik pivot formülünü doğru uygular', () => {
    const p = computePivots(series, TODAY)!.monthly!;
    const [h, l, c] = [130, 70, 120];
    const pivot = (h + l + c) / 3;
    expect(p.pivot).toBeCloseTo(pivot, 10);
    expect(p.classic.r1).toBeCloseTo(2 * pivot - l, 10);
    expect(p.classic.s1).toBeCloseTo(2 * pivot - h, 10);
    expect(p.classic.r2).toBeCloseTo(pivot + (h - l), 10);
    expect(p.classic.s2).toBeCloseTo(pivot - (h - l), 10);
  });

  it('Fibonacci seviyeleri aralığın 0,382 / 0,618 / 1,0 katıdır', () => {
    const p = computePivots(series, TODAY)!.monthly!;
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

describe('tamamlanmış dönem seçimi', () => {
  /** Pazartesi–cuma beş mumluk haftalar üretir. */
  const week = (monday: string, base: number): Candle[] =>
    Array.from({ length: 5 }, (_, i) => {
      const d = new Date(`${monday}T00:00:00Z`);
      d.setUTCDate(d.getUTCDate() + i);
      return { date: d.toISOString().slice(0, 10), h: base + 10 + i, l: base - 10 + i, c: base + i };
    });

  /* 40 mum alt sınırını aşmak için 10 hafta; son dördü ölçülen değerlerle aynı. */
  const candles = [
    ...['2026-06-08', '2026-06-15', '2026-06-22', '2026-06-29', '2026-07-06', '2026-07-13', '2026-07-20']
      .flatMap((monday, i) => week(monday, 3900 + i * 20)),
    ...week('2026-07-27', 4050), ...week('2026-08-03', 4340),
    ...week('2026-08-10', 4380), ...week('2026-08-17', 4620),
  ];

  /* Kod her zaman sondan bir önceki grubu alıyordu: cuma kapanmış olsa bile
     içinde bulunulan hafta "devam ediyor" sayılıyor, seviyeler bir hafta
     bayat kalıyordu. 22 Ağustos cumartesi, 17–21 haftası tamamlanmıştır. */
  it('hafta cuma kapanışıyla tamamlanmış sayılır', () => {
    expect(computePivots(candles, '2026-08-22')!.weekly!.id).toBe('2026-08-17');
    expect(computePivots(candles, '2026-08-24')!.weekly!.id).toBe('2026-08-17');
  });

  it('hafta sürerken bir önceki hafta kullanılır', () => {
    expect(computePivots(candles, '2026-08-19')!.weekly!.id).toBe('2026-08-10');
    expect(computePivots(candles, '2026-08-17')!.weekly!.id).toBe('2026-08-10');
  });

  it('ay ancak bittiğinde tamamlanmış sayılır', () => {
    expect(computePivots(candles, '2026-08-22')!.monthly!.id).toBe('2026-07');
    expect(computePivots(candles, '2026-09-01')!.monthly!.id).toBe('2026-08');
  });

  it('hiçbir dönem tamamlanmadıysa null döner', () => {
    // 40 mum var ama "bugün" ilk haftanın içinde: tamamlanmış hafta yok.
    // Bugün ilk haftanın içinde: 40+ mum var ama tamamlanmış hafta yok.
    expect(computePivots(candles, '2026-06-10')!.weekly).toBeNull();
  });

  it('seçilen dönemin yüksek/düşük/kapanışı doğru toplanır', () => {
    const set = computePivots(candles, '2026-08-22')!.weekly!;
    // 17–21 haftası: h = 4620+10+4, l = 4620-10, c = 4620+4
    const h = 4634, l = 4610, c = 4624;
    expect(set.pivot).toBeCloseTo((h + l + c) / 3, 9);
    expect(set.classic.r1).toBeCloseTo(2 * ((h + l + c) / 3) - l, 9);
  });
});
