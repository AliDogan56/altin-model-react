import { predict } from './predict';
import type { FeatureMap, ModelArtifact } from './types';

export type Impact = { name: string; key: string; value: number; z: number; share: number };
export type Impacts = { rows: Impact[]; here: number; constant: number; total: number };

/** Her satır şunu ölçer: bu girdi ortalamasına çekilseydi 1 aylık tahmin ne kadar değişirdi.
 *  Karşılaştırmanın iki ucu da aynı modelden gelmeli; önceden taban sunucu tahminiydi,
 *  fark ise tarayıcı modeliyle hesaplanıyordu ve model farkı da katkı gibi görünüyordu. */
export const computeImpacts = (
  model: ModelArtifact, features: FeatureMap, price: number, names: Record<string, string>,
): Impacts => {
  const at = (f: FeatureMap) => predict(model, f, price).mean[1];
  const here = at(features);

  const atMean: FeatureMap = { ...features };
  model.features.forEach((k, i) => { atMean[k] = model.xMean[i]; });
  const constant = at(atMean);

  const rows = Object.entries(names).map(([key, name]) => {
    const index = model.features.indexOf(key);
    const changed: FeatureMap = { ...features, [key]: model.xMean[index] };
    changed.yield_curve_10y_2y = changed.DGS10 - changed.DGS2;
    changed.breakeven_inflation_10y = changed.DGS10 - changed.DFII10;
    return {
      name, key, value: here - at(changed),
      z: model.xStd[index] ? (features[key] - model.xMean[index]) / model.xStd[index] : 0,
    };
  }).sort((a, b) => Math.abs(b.value) - Math.abs(a.value));

  const peak = Math.max(...rows.map(r => Math.abs(r.value)), 1e-9);
  return { rows: rows.map(r => ({ ...r, share: Math.abs(r.value) / peak })), here, constant, total: here - constant };
};
