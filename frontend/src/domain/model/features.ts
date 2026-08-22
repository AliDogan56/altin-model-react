import type { FeatureMap, ModelArtifact } from './types';

/** Yüzde olarak girilen alanlar; arayüzde 100 ile çarpılı tutulur, modele oranla gider. */
export const PCT_FIELDS = new Set([
  'gold_return_1d', 'gold_return_5d', 'gold_return_20d', 'gold_ma_ratio_50d',
  'gold_atr14_pct', 'gold_volatility_20d', 'gold_drawdown_60d',
  'dollar_return_5d', 'dollar_return_20d', 'oil_return_5d', 'oil_return_20d',
]);

export const computeFeatures = (
  model: ModelArtifact, values: Record<string, unknown>, live: FeatureMap,
): FeatureMap => {
  const f: FeatureMap = { ...model.latest, ...live };
  Object.entries(values).forEach(([k, v]) => {
    if (k !== 'price') f[k] = PCT_FIELDS.has(k) ? +(v as number) / 100 : +(v as number);
  });
  return f;
};
