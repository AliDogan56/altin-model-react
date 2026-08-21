import { describe, expect, it } from 'vitest';
import { emaSeries, sma, wilder } from './math';
import { indicators, type Candle } from './index';

/** Deterministik mum serisi: testler canlı veriye bağlı olmamalı. */
const candles = (n: number): Candle[] =>
  Array.from({ length: n }, (_, i) => {
    const c = 1000 + Math.sin(i / 7) * 40 + i * 0.5;
    return { date: `2026-01-${String((i % 28) + 1).padStart(2, '0')}`, h: c + 6, l: c - 6, c };
  });

describe('yardımcılar', () => {
  it('sma pencere dolmadan null döner', () => {
    expect(sma([1, 2], 3)).toBeNull();
    expect(sma([1, 2, 3], 3)).toBe(2);
  });
  it('emaSeries ilk n-1 değeri null bırakır', () => {
    const out = emaSeries([1, 2, 3, 4], 3);
    expect(out.slice(0, 2)).toEqual([null, null]);
    expect(out[3]).toBeGreaterThan(0);
  });
  it('wilder ilk n değerin toplamıyla başlar', () => {
    expect(wilder([2, 2, 2], 3)[2]).toBe(6);
    expect(wilder([1], 3)).toEqual([null]);
  });
});

describe('indicators', () => {
  it('yetersiz mum sayısında null döner', () => {
    expect(indicators(candles(209))).toBeNull();
  });

  it('her satır gerçek bir değer taşır', () => {
    // state() yardımcısı value da döndürdüğü için nesne yayılımında tüm
    // göstergeler "0" görünmüştü; bu test o regresyonu kilitler.
    const out = indicators(candles(260))!;
    expect(out.rows).toHaveLength(8);
    out.rows.forEach(row => {
      expect(row.value).not.toBe('0');
      expect(row.value).not.toBe('');
      expect(row.text.length).toBeGreaterThan(0);
    });
  });

  it('Williams %R ile Stochastic %K birbirini doğrular', () => {
    // Williams %R = −(100 − %K). İki bağımsız formülün tutması hesabın kanıtı.
    const out = indicators(candles(260))!;
    const k = Number(out.rows.find(r => r.name.startsWith('Stochastic'))!.value);
    const w = Number(out.rows.find(r => r.name.startsWith('Williams'))!.value);
    expect(w).toBeCloseTo(-(100 - k), 4);
  });

  it('göstergeler geçerli aralıkta kalır', () => {
    const out = indicators(candles(300))!;
    const val = (prefix: string) => Number(out.rows.find(r => r.name.startsWith(prefix))!.value);
    expect(val('RSI')).toBeGreaterThanOrEqual(0);
    expect(val('RSI')).toBeLessThanOrEqual(100);
    expect(val('Stochastic')).toBeGreaterThanOrEqual(0);
    expect(val('Stochastic')).toBeLessThanOrEqual(100);
    expect(val('Williams')).toBeGreaterThanOrEqual(-100);
    expect(val('Williams')).toBeLessThanOrEqual(0);
    expect(val('ADX')).toBeGreaterThanOrEqual(0);
    expect(val('ADX')).toBeLessThanOrEqual(100);
  });

  it('hareketli ortalamalar yalnız hesaplanabilenleri döner', () => {
    const out = indicators(candles(260))!;
    expect(out.averages.map(a => a.n)).toEqual([5, 10, 20, 50, 100, 200]);
    out.averages.forEach(a => expect(a.sma).not.toBeNull());
  });
});
