import { describe, expect, it } from 'vitest';
import { parseForecast } from './model';

const valid = { horizons: [7, 14, 30], mean: [0.01, 0.02, 0.03], error: [0.03, 0.04, 0.05] };

describe('parseForecast', () => {
  it('geçerli yanıtı alanlarıyla birlikte döner', () => {
    const result = parseForecast({ ...valid, version: 'v1', weights: [0.9, 0.1, 0.6],
      confident: [true, false, true], clipped_features: ['vix_level'] });
    expect(result).toEqual({
      horizons: [7, 14, 30], mean: [0.01, 0.02, 0.03], err: [0.03, 0.04, 0.05],
      version: 'v1', weights: [0.9, 0.1, 0.6], confident: [true, false, true],
      clipped: ['vix_level'], featureEffects: undefined,
    });
  });

  it('ağırlık gelmezse hepsini güvenli sayar', () => {
    const result = parseForecast(valid)!;
    expect(result.weights).toEqual([1, 1, 1]);
    expect(result.confident).toEqual([true, true, true]);
  });

  /* Eksik `horizons` alanı `forecast.horizons.indexOf(...)` üzerinden fırlıyor ve
     ErrorBoundary olmadığı için tüm sayfayı beyaza düşürüyordu. */
  it('bozuk yanıtı reddeder, fırlatmaz', () => {
    expect(parseForecast({ mean: [0.01], error: [0.02] })).toBeNull();
    expect(parseForecast({ horizons: [7], mean: [0.01] })).toBeNull();
    expect(parseForecast({ horizons: [7], mean: [0.01], error: [] })).toBeNull();
    expect(parseForecast(null)).toBeNull();
    expect(parseForecast('yanıt değil')).toBeNull();
  });

  it('uzunluğu tutmayan diziler reddedilir', () => {
    expect(parseForecast({ horizons: [7, 14], mean: [0.01], error: [0.02, 0.03] })).toBeNull();
  });

  it('sayı olmayan değer reddedilir', () => {
    expect(parseForecast({ horizons: [7], mean: ['x'], error: [0.02] })).toBeNull();
    expect(parseForecast({ horizons: [7], mean: [NaN], error: [0.02] })).toBeNull();
  });
});
