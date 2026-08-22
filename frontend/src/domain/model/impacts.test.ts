import { describe, expect, it } from 'vitest';
import { computeImpacts } from './impacts';
import type { ModelArtifact } from './types';

/** Tek girdisi çıkışa bağlı doğrusal sahte model: katkılar elle doğrulanabilir. */
const fake = (): ModelArtifact => ({
  features: ['DGS10', 'DGS2', 'DFII10', 'VIXCLS'],
  horizons: [7, 30],
  xMean: [4, 4, 2, 20], xStd: [1, 1, 1, 5],
  yMean: [0, 0], yStd: [1, 1],
  models: [{ w1: [[1], [0], [0], [0]], b1: [0], w2: [[1]], b2: [0], w3: [[1, 2]], b3: [0, 0] }],
  residual80: [0.01, 0.02],
  latest: {}, latestPrice: 100, latestDate: '2026-08-14', history: [],
  resistance: { r20: 0, r60: 0, momentumJumpPct: 0 },
});

const features = { DGS10: 6, DGS2: 4, DFII10: 2, VIXCLS: 20 };
const labels = { DGS10: { label: '10 yıllık faiz', hint: 'neden önemli' } };

describe('computeImpacts', () => {
  /* Kart eskiden sabit 14 girdilik bir sözlükten besleniyordu ve en büyük etki
     (drawdown) listede hiç yer almıyordu; artık kaynak modelin kendi girdi listesi. */
  it('etkisi olan her girdiyi listeler, sözlükte olmasa bile', () => {
    const r = computeImpacts(fake(), features, 100, {});
    const keys = [...r.up, ...r.down].map(x => x.key);
    expect(keys).toContain('DGS10');
    expect(keys.length).toBe(1);          // sahte modelde yalnız DGS10 çıkışa bağlı
  });

  it('etkisi sıfır olan girdi listeyi kalabalıklaştırmaz', () => {
    const r = computeImpacts(fake(), features, 100, {});
    expect([...r.up, ...r.down].some(x => x.value === 0)).toBe(false);
  });

  it('sade dil sözlüğünden etiket ve açıklama alır', () => {
    const r = computeImpacts(fake(), features, 100, labels);
    const row = [...r.up, ...r.down].find(x => x.key === 'DGS10')!;
    expect(row.label).toBe('10 yıllık faiz');
    expect(row.hint).toBe('neden önemli');
  });

  it('yukarı itenler ve aşağı çekenler ayrılır, büyükten küçüğe sıralanır', () => {
    const r = computeImpacts(fake(), features, 100, labels);
    expect(r.up.every(x => x.value > 0)).toBe(true);
    expect(r.down.every(x => x.value < 0)).toBe(true);
    expect(r.up[0].share).toBe(1);
  });

  it('dolar karşılığı fiyatla ölçeklenir', () => {
    const r = computeImpacts(fake(), features, 200, labels);
    const row = r.up.find(x => x.key === 'DGS10')!;
    expect(row.usd).toBeCloseTo(row.value * 200, 12);
  });

  it('net etki, yukarı ve aşağı toplamların farkıdır', () => {
    const r = computeImpacts(fake(), features, 100, labels);
    expect(r.netUsd).toBeCloseTo(r.upUsd + r.downUsd, 12);
  });

  it('sıra dışılık standart sapmaya göre etiketlenir', () => {
    // DGS10: z = (6-4)/1 = 2 -> extreme
    const extreme = computeImpacts(fake(), features, 100, labels);
    expect([...extreme.up, ...extreme.down].find(x => x.key === 'DGS10')!.unusualness).toBe('extreme');
    // z = 0.7 -> high, z = 0.2 -> normal
    const high = computeImpacts(fake(), { ...features, DGS10: 4.7 }, 100, labels);
    expect([...high.up, ...high.down].find(x => x.key === 'DGS10')!.unusualness).toBe('high');
    const normal = computeImpacts(fake(), { ...features, DGS10: 4.2 }, 100, labels);
    expect([...normal.up, ...normal.down].find(x => x.key === 'DGS10')!.unusualness).toBe('normal');
  });

  it('sunucu etkisi varsa nötr tarayıcı hesabı yerine onu kullanır', () => {
    const forecast = { horizons: [7, 30], features, price: 100, mean: [0, .05], err: [.02, .04],
      featureEffects: { '30': { DGS10: .012, DGS2: -.004 } } };
    const r = computeImpacts(fake(), features, 100, labels, forecast, 30);
    expect(r.live).toBe(true);
    expect(r.up.find(x => x.key === 'DGS10')!.value).toBeCloseTo(.012, 12);
    expect(r.here).toBeCloseTo(.05, 12);
  });
});

describe('görünürlük eşiği', () => {
  it('dolar karşılığı yuvarlandığında sıfır olan satır listelenmez', () => {
    const forecast = { horizons: [7, 30], features, price: 100, mean: [0, .05], err: [.02, .04],
      featureEffects: { '30': { DGS10: .012, DGS2: -.000002, DFII10: .05 } } };
    const r = computeImpacts(fake(), features, 100, labels, forecast, 30);
    const keys = [...r.up, ...r.down].map(x => x.key);
    expect(keys).toContain('DGS10');
    expect(keys).toContain('DFII10');
    expect(keys).not.toContain('DGS2');       // 100 × -0.000002 = -$0.0002
  });

  it('gizlenen satır toplamlardan düşülmez', () => {
    const forecast = { horizons: [7, 30], features, price: 100, mean: [0, .05], err: [.02, .04],
      featureEffects: { '30': { DGS10: .012, DGS2: -.000002 } } };
    const r = computeImpacts(fake(), features, 100, labels, forecast, 30);
    expect(r.downUsd).toBeCloseTo(-0.0002, 9);
    expect(r.down).toHaveLength(0);
  });
});
