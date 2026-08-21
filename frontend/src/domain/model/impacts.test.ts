import { describe, expect, it } from 'vitest';
import { computeImpacts } from './impacts';
import type { ModelArtifact } from './types';

/** İki girdili, tek katmanlı doğrusal sahte model: katkılar elle doğrulanabilir. */
const fake = (): ModelArtifact => ({
  features: ['DGS10', 'DGS2', 'DFII10', 'VIXCLS', 'yield_curve_10y_2y', 'breakeven_inflation_10y'],
  horizons: [7, 30],
  xMean: [4, 4, 2, 20, 0, 2], xStd: [1, 1, 1, 5, 1, 1],
  yMean: [0, 0], yStd: [1, 1],
  models: [{
    w1: [[1], [0], [0], [0], [0], [0]], b1: [0],
    w2: [[1]], b2: [0],
    w3: [[1, 2]], b3: [0, 0],
  }],
  residual80: [0.01, 0.02],
  latest: {}, latestPrice: 100, latestDate: '2026-08-14', history: [],
  resistance: { r20: 0, r60: 0, momentumJumpPct: 0 },
});

const features = { DGS10: 6, DGS2: 4, DFII10: 2, VIXCLS: 20, yield_curve_10y_2y: 2, breakeven_inflation_10y: 4 };

describe('computeImpacts', () => {
  it('değeri ortalamada olan girdinin katkısı sıfırdır', () => {
    const r = computeImpacts(fake(), features, 100, { VIXCLS: 'VIX' });
    expect(r.rows[0].value).toBeCloseTo(0, 12);
    expect(r.rows[0].z).toBeCloseTo(0, 12);
  });

  it('katkı, girdiyi ortalamasına çekmenin tahmine etkisidir', () => {
    const r = computeImpacts(fake(), features, 100, { DGS10: '10Y' });
    // ilk ağırlık yalnız DGS10'u taşıyor: z = (6-4)/1 = 2, 30g çıkışı 2×z farkı
    expect(r.rows[0].z).toBeCloseTo(2, 12);
    expect(r.rows[0].value).toBeCloseTo(4, 12);
  });

  it('satırlar mutlak katkıya göre sıralanır ve pay 1 ile normalize edilir', () => {
    const r = computeImpacts(fake(), features, 100, { VIXCLS: 'VIX', DGS10: '10Y' });
    expect(r.rows.map(x => x.key)).toEqual(['DGS10', 'VIXCLS']);
    expect(r.rows[0].share).toBe(1);
  });

  it('toplam, tüm girdiler ortalamadayken kalan sabitten sapmadır', () => {
    const r = computeImpacts(fake(), features, 100, { DGS10: '10Y' });
    expect(r.total).toBeCloseTo(r.here - r.constant, 12);
  });
});
