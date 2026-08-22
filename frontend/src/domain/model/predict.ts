import { avg, clamp, std } from '../../lib/math';
import { forward } from './network';
import type { FeatureMap, Forecast, ModelArtifact, PathPoint } from './types';

/** Bant ölçeği: residual80 %80'lik artık, %70 banda çekmek için daraltılır. */
export const BAND_SCALE = 0.81;
export const BAND_COVERAGE = 70;

export const predict = (model: ModelArtifact, features: FeatureMap, price: number): Forecast => {
  const x = model.features.map((k, i) => clamp((features[k] - model.xMean[i]) / model.xStd[i], -6, 6));
  const all = model.models.map(net => forward(x, net, model.yMean, model.yStd));
  const mean = model.horizons.map((_, j) => avg(all.map(p => p[j])));
  const err = model.residual80.map((r, j) => Math.max(r, std(all.map(p => p[j])) * 1.64) * BAND_SCALE);
  return { horizons: model.horizons, features, price: +price, mean, err };
};

/**
 * Tahmin yolu, geçmiş serisinin bittiği günden başlar. Tarihleri `new Date()` ile
 * üretmek, geçmiş bir sebeple geride kaldığında takvimde boşluk gösteriyordu
 * (geçmiş 14'te bitip tahmin 19'dan başlaması gibi).
 */
export const buildDailyPath = (
  model: ModelArtifact, forecast: Forecast, horizonDays: number, startDate: string | null = null,
): PathPoint[] => {
  const anchors = [{ day: 0, ret: 0, err: 0 },
    ...forecast.horizons.map((day, j) => ({ day, ret: forecast.mean[j], err: forecast.err[j] }))];
  return Array.from({ length: horizonDays + 1 }, (_, day) => {
    const right = anchors.find(a => a.day >= day) || anchors.at(-1)!;
    const ri = anchors.indexOf(right);
    const left = anchors[Math.max(0, ri - 1)];
    const t = right.day === left.day ? 0 : (day - left.day) / (right.day - left.day);
    const ret = Math.expm1(Math.log1p(Math.max(-0.95, left.ret)) * (1 - t) + Math.log1p(Math.max(-0.95, right.ret)) * t);
    const err = left.err * (1 - t) + right.err * t;
    const date = startDate ? new Date(`${startDate}T00:00:00Z`) : new Date();
    if (startDate) date.setUTCDate(date.getUTCDate() + day); else date.setDate(date.getDate() + day);
    return {
      day, date: date.toISOString().slice(0, 10),
      v: forecast.price * (1 + ret),
      lo: forecast.price * (1 + ret - err),
      hi: forecast.price * (1 + ret + err),
      ret, err, kind: 'Günlükleştirilmiş tahmin',
    };
  });
};
