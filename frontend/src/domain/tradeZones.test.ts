import { describe, expect, it } from 'vitest';
import { tradeZones } from './tradeZones';
import type { Forecast } from './model/types';

const forecast = (mean1: number, err1: number): Forecast =>
  ({ horizons: [7, 30], features: {}, price: 100, mean: [0, mean1], err: [0, err1] });

describe('tradeZones', () => {
  it('alım bölgesi tahminin altında, satış üstündedir', () => {
    const z = tradeZones(forecast(0.05, 0.06), 100, 0.01, 10_000, 1);
    expect(z.near).toBeCloseTo(105, 12);
    expect(z.buy[0]).toBeLessThan(z.buy[1]);
    expect(z.buy[1]).toBeLessThan(z.near);
    expect(z.near).toBeLessThan(z.sell[0]);
    expect(z.sell[0]).toBeLessThan(z.sell[1]);
  });

  it('zarar kes daima alım bölgesinin altındadır', () => {
    const z = tradeZones(forecast(0.05, 0.06), 100, 0.03, 10_000, 1);
    expect(z.stop).toBeLessThan(z.buy[0]);
  });

  it('oynaklık büyüdükçe zarar kes uzaklaşır ve pozisyon küçülür', () => {
    const dar = tradeZones(forecast(0.05, 0.06), 100, 0.005, 10_000, 1);
    const genis = tradeZones(forecast(0.05, 0.06), 100, 0.05, 10_000, 1);
    expect(genis.stop).toBeLessThan(dar.stop);
    expect(genis.units).toBeLessThan(dar.units);
  });

  it('pozisyon büyüklüğü risk bütçesiyle orantılıdır', () => {
    const bir = tradeZones(forecast(0.05, 0.06), 100, 0.01, 10_000, 1);
    const iki = tradeZones(forecast(0.05, 0.06), 100, 0.01, 10_000, 2);
    expect(iki.units).toBeCloseTo(bir.units * 2, 9);
  });
});
