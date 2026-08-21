import { describe, expect, it } from 'vitest';
import { buildScorecard, type SettledPoint } from './scorecard';

const row = (v: number, real: number | undefined, lo = 0, hi = 1e9): SettledPoint => ({
  day: 1, date: '2026-08-15', v, lo, hi, ret: 0, err: 0, kind: 't',
  real, errorPct: real == null ? null : (v - real) / real,
});

describe('buildScorecard', () => {
  it('vadesi dolan gün yoksa null döner', () => {
    expect(buildScorecard([row(100, undefined)], 100)).toBeNull();
  });

  it('tahmin naif kuralla aynıysa beceri sıfırdır', () => {
    // Model baz fiyatı tekrarlıyorsa hiçbir bilgi katmıyor demektir.
    const base = 100;
    const table = [row(base, 105), row(base, 95)];
    const s = buildScorecard(table, base)!;
    expect(s.mae).toBeCloseTo(s.naiveMae, 12);
    expect(s.skill).toBeCloseTo(0, 12);
  });

  it('tahmin gerçekleşene daha yakınsa beceri pozitiftir', () => {
    const s = buildScorecard([row(104, 105), row(96, 95)], 100)!;
    expect(s.skill).toBeGreaterThan(0);
  });

  it('bant ve yön isabetini sayar', () => {
    const s = buildScorecard([
      row(110, 105, 100, 120),   // bant içinde, yön doğru (ikisi de 100'ün üstünde)
      row(110, 90, 100, 120),    // bant dışında, yön yanlış
    ], 100)!;
    expect(s.days).toBe(2);
    expect(s.inBand).toBe(1);
    expect(s.rightWay).toBe(1);
  });

  it('en büyük sapmayı mutlak değere göre seçer', () => {
    const s = buildScorecard([row(101, 100), row(80, 100)], 100)!;
    expect(s.worst.v).toBe(80);
  });
});
