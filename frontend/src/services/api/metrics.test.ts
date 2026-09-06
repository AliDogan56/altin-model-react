import { describe, expect, it } from 'vitest';
import { parseScorecard } from './metrics';

const payload = {
  active_model: 'xauusd-mlp-20260821T164355Z',
  horizons: [7, 14, 30],
  metrics: {
    '7': { mae: 0.0232, direction: 0.635, skill_vs_zero: 0.0386, weight: 0.923,
           within_2pp: 0.5307, error80: 0.0355, oof_rows: 537 },
    '14': { mae: 0.0317, direction: 0.624, skill_vs_zero: 0.0187, weight: 0.130,
            within_2pp: 0.4112, error80: 0.0486, oof_rows: 535 },
  },
};

describe('parseScorecard', () => {
  it('yeni MAE skill ile eski MSE skill tanımlarını karıştırmaz', () => {
    const raw = { ...payload, metrics: { '7': { ...payload.metrics['7'], mae_skill_vs_zero: -.01 } } };
    expect(parseScorecard(raw)!.rows[0].skill).toBe(-.01);
    expect(parseScorecard(raw)!.rows[0].skillBasis).toBe('MAE');
    expect(parseScorecard(payload)!.rows[0].skillBasis).toBe('MSE');
  });
  it('koşullu yön örneklemini ve yeni değerlendirme sürümünü korur', () => {
    const raw = { ...payload, metrics: { '7': { ...payload.metrics['7'], active_fraction: .4,
      directional_rows: 200, evaluation_version: 'nested-purged-v1' } } };
    const row = parseScorecard(raw)!.rows[0];
    expect(row.activeFraction).toBe(.4);
    expect(row.directionalRows).toBe(200);
    expect(row.evaluationVersion).toBe('nested-purged-v1');
    expect(parseScorecard(payload)!.rows[0].evaluationVersion).toBeNull();
    expect(parseScorecard(payload)!.rows[0].activeFraction).toBeNull();
  });
  it('ağırlığı sıfır olan görüş-yok ufkunu karneden gizlemez', () => {
    const raw = { ...payload, metrics: { '7': { ...payload.metrics['7'], direction: null, weight: 0 } } };
    const row = parseScorecard(raw)!.rows[0];
    expect(row.direction).toBeNull();
    expect(row.confident).toBe(false);
  });
  it('ufuk başına satır üretir ve ağırlığa göre güven işaretler', () => {
    const card = parseScorecard(payload)!;
    expect(card.version).toBe('xauusd-mlp-20260821T164355Z');
    expect(card.rows.map(r => r.horizon)).toEqual([7, 14]);
    expect(card.rows[0].confident).toBe(true);
    expect(card.rows[1].confident).toBe(false);
    expect(card.rows[0].oofRows).toBe(537);
  });

  it('ölçüm satırı yoksa null döner — boş kart çizilmesin', () => {
    expect(parseScorecard({ ...payload, metrics: {} })).toBeNull();
    expect(parseScorecard(null)).toBeNull();
    expect(parseScorecard({ horizons: [7] })).toBeNull();
  });

  it('eksik alanlı ufku atlar', () => {
    const card = parseScorecard({ ...payload, metrics: { ...payload.metrics, '30': { mae: 'x' } } })!;
    expect(card.rows.map(r => r.horizon)).toEqual([7, 14]);
  });

  it('en çok ölçülen ufku toplam gün sayısı olarak verir', () => {
    expect(parseScorecard(payload)!.measuredDays).toBe(537);
  });
});
