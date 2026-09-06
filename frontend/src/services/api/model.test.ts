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
      clipped: ['vix_level'], neutralized: [], featureEffects: undefined,
      intervalCoverage: [null, null, null], originDate: undefined, predictionTimestamp: undefined,
      basePrice: undefined, status: undefined, noViewReasons: [[], [], []],
    });
  });

  /* Donmuş girdiler tahmine katılmıyor; arayüz hangisinin dışarıda kaldığını
     yazabilmek için bu listeyi okur. */
  it('nötrlenen girdileri okur', () => {
    const result = parseForecast({ ...valid, neutralized_features: ['core_cpi_yoy'] })!;
    expect(result.neutralized).toEqual(['core_cpi_yoy']);
  });

  it('nötrlenen girdi listesi bozuksa boş sayılır', () => {
    expect(parseForecast({ ...valid, neutralized_features: 'core_cpi_yoy' })!.neutralized).toEqual([]);
    expect(parseForecast({ ...valid, neutralized_features: [1, 'core_cpi_yoy'] })!.neutralized)
      .toEqual(['core_cpi_yoy']);
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

  /* İşlem bölgeleri sunucuda hesaplanır; görüşsüz ufuk `null` gelir. */
  it('işlem bölgelerini ufuk başına okur, görüşsüz ufku null bırakır', () => {
    const result = parseForecast({ ...valid, scenario_zones: {
      '7': null, '14': null,
      '30': { near: 4556.88, band: 501.71, atr: 91.06, buy: [4195.65, 4366.23], sell: [4732.48, 4918.11],
              stop: 4059.05, entry: 4280.94, risk_per_unit: 221.89, params_version: 'scenario-v1' },
    } })!;
    expect(result.scenarioZones).toEqual({
      '7': null, '14': null,
      '30': { near: 4556.88, band: 501.71, atr: 91.06, buy: [4195.65, 4366.23], sell: [4732.48, 4918.11],
              stop: 4059.05, entry: 4280.94, riskPerUnit: 221.89, paramsVersion: 'scenario-v1' },
    });
  });

  /* Bozuk bölge haritası tahminin kendisini düşürmemeli; alan yalnız `undefined` kalır. */
  it('bozuk ya da eksik işlem bölgeleri tahmini reddetmez, alan undefined kalır', () => {
    expect(parseForecast(valid)!.scenarioZones).toBeUndefined();
    expect(parseForecast({ ...valid, scenario_zones: 'çöp' })!.scenarioZones).toBeUndefined();
    const half = { near: 4556.88, band: 501.71, atr: 91.06, buy: [4195.65], sell: [4732.48, 4918.11],
                   stop: 4059.05, entry: 4280.94, risk_per_unit: 221.89, params_version: 'scenario-v1' };
    const result = parseForecast({ ...valid, scenario_zones: { '7': null, '30': half } })!;
    expect(result).not.toBeNull();
    expect(result.scenarioZones).toBeUndefined();
    expect(parseForecast({ ...valid, scenario_zones: { '30': { ...half, buy: [1, 2], near: 'x' } } })!.scenarioZones)
      .toBeUndefined();
  });

  it('sunucunun yüzde 80 nominal bandını daraltmadan ve yüzde 70 diye etiketlemeden taşır', () => {
    const result = parseForecast({ ...valid, base_price: 4500, origin_date: '2026-09-05',
      intervals: [{ nominal_coverage: .8 }, { nominal_coverage: .8 }, { nominal_coverage: .8 }] })!;
    expect(result.intervalCoverage).toEqual([.8, .8, .8]);
    expect(result.err).toEqual(valid.error);
    expect(result.basePrice).toBe(4500);
    expect(result.originDate).toBe('2026-09-05');
  });
});
