import { describe, expect, it } from 'vitest';
import { buildDailyPath, predict } from './predict';
import { computeFeatures } from './features';
import type { ModelArtifact } from './types';

/** İki girdi, iki ufuk, tek ağ: çıktısı elle doğrulanabilir minik model. */
const model: ModelArtifact = {
  features: ['a', 'b'],
  horizons: [7, 30],
  xMean: [0, 0], xStd: [1, 1],
  yMean: [0, 0], yStd: [1, 1],
  models: [{ w1: [[1, 0], [0, 1]], b1: [0, 0], w2: [[1, 0], [0, 1]], b2: [0, 0], w3: [[1, 0], [0, 1]], b3: [0, 0] }],
  residual80: [0.02, 0.05],
  latest: { a: 0, b: 0, DGS10: 4, DGS2: 3, DFII10: 2 },
  latestPrice: 1000, latestDate: '2026-08-14',
  history: [['2026-08-14', 1000]],
  resistance: { r20: 1, r60: 1, momentumJumpPct: 0 },
};

describe('predict', () => {
  it('relu ağı üzerinden beklenen getiriyi üretir', () => {
    const out = predict(model, { a: 0.1, b: 0.2 }, 1000);
    expect(out.mean).toEqual([0.1, 0.2]);        // birim matrisler: girdi = çıktı
    expect(out.price).toBe(1000);
  });

  it('girdileri ±6 standart sapmada kırpar', () => {
    const out = predict(model, { a: 999, b: -999 }, 1000);
    expect(out.mean[0]).toBe(6);
    expect(out.mean[1]).toBe(0);                 // relu negatifi keser
  });

  it('bant en az residual80 kadardır', () => {
    const out = predict(model, { a: 0, b: 0 }, 1000);
    expect(out.err[0]).toBeCloseTo(0.02 * 0.81, 10);
    expect(out.err[1]).toBeCloseTo(0.05 * 0.81, 10);
  });
});

describe('buildDailyPath', () => {
  const forecast = predict(model, { a: 0.1, b: 0.2 }, 1000);

  it('gün 0 baz fiyattan başlar', () => {
    const path = buildDailyPath(model, forecast, 30);
    expect(path[0].v).toBeCloseTo(1000, 6);
    expect(path[0].ret).toBeCloseTo(0, 10);
  });

  it('başlangıç günü verildiğinde takvim kesintisiz ilerler', () => {
    // Tarihler `new Date()` ile üretildiğinde geçmiş 14'te bitip tahmin 19'dan
    // başlıyordu; bu test o boşluğun geri gelmesini engeller.
    const path = buildDailyPath(model, forecast, 5, '2026-08-14');
    expect(path.map(p => p.date)).toEqual([
      '2026-08-14', '2026-08-15', '2026-08-16', '2026-08-17', '2026-08-18', '2026-08-19',
    ]);
  });

  it('ay ve yıl sınırını doğru geçer', () => {
    expect(buildDailyPath(model, forecast, 2, '2026-08-30').map(p => p.date))
      .toEqual(['2026-08-30', '2026-08-31', '2026-09-01']);
    expect(buildDailyPath(model, forecast, 2, '2026-12-30').map(p => p.date))
      .toEqual(['2026-12-30', '2026-12-31', '2027-01-01']);
  });

  it('bant ufukla birlikte genişler', () => {
    const path = buildDailyPath(model, forecast, 30, '2026-08-14');
    const width = (i: number) => path[i].hi - path[i].lo;
    expect(width(30)).toBeGreaterThan(width(7));
    expect(width(7)).toBeGreaterThan(width(1));
  });

  it('ufuk uzunluğu kadar +1 nokta üretir', () => {
    expect(buildDailyPath(model, forecast, 90, '2026-01-01')).toHaveLength(91);
  });
});

describe('computeFeatures', () => {
  /* Türetilmiş alan kalmadı: yield_curve_10y_2y artık macroFeatures'tan hazır
     geliyor, breakeven_inflation_10y ise XAU feature setinden tamamen çıktı. */
  it('canlı değerin üzerine form değerini yazar', () => {
    const f = computeFeatures(model, { yield_curve_10y_2y: 1.4 }, { yield_curve_10y_2y: 0.9, vix_level: 17 });
    expect(f.yield_curve_10y_2y).toBe(1.4);
    expect(f.vix_level).toBe(17);
  });

  it('yüzde alanlarını orana çevirir, price alanını yok sayar', () => {
    const f = computeFeatures(model, { gold_return_20d: 250, price: 9999 }, {});
    expect(f.gold_return_20d).toBe(2.5);
    expect(f.price).toBeUndefined();
  });
});
