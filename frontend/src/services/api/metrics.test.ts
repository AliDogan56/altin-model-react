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
