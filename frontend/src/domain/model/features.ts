import type { FeatureMap, ModelArtifact } from './types';

/** Yüzde olarak girilen alanlar; arayüzde 100 ile çarpılı tutulur, modele oranla gider. */
export const PCT_FIELDS = new Set(['gold_atr14_pct', 'gold_return_20d', 'gold_volatility_20d']);

export const computeFeatures = (
  model: ModelArtifact, values: Record<string, unknown>, live: FeatureMap,
): FeatureMap => {
  const f: FeatureMap = { ...model.latest, ...live };
  Object.entries(values).forEach(([k, v]) => {
    if (k !== 'price') f[k] = PCT_FIELDS.has(k) ? +(v as number) / 100 : +(v as number);
  });
  f.yield_curve_10y_2y = f.DGS10 - f.DGS2;
  f.breakeven_inflation_10y = f.DGS10 - f.DFII10;
  return f;
};
