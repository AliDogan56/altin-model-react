import { avg } from '../lib/math';
import { buildDailyPath } from './model/predict';
import type { Forecast, ModelArtifact, PathPoint } from './model/types';

export type SettledPoint = PathPoint & { real?: number; errorPct: number | null };

/**
 * Modelin ilk yayınladığı tahmin, o günkü girdilerle hesaplanır ve gerçekleşen
 * kapanışlarla eşleştirilir. Canlı girdilerle yeniden hesaplamak, geçmişi bugünün
 * bilgisiyle tahmin etmek olurdu.
 */
export const buildForecastTable = (
  model: ModelArtifact, originForecast: Forecast, history: [string, number][], horizonDays: number,
): SettledPoint[] => {
  const actual = new Map<string, number>(history.map(([date, value]) => [String(date), Number(value)]));
  return buildDailyPath(model, { ...originForecast, price: model.latestPrice }, horizonDays, model.latestDate)
    .slice(1)
    .map(point => {
      const real = actual.get(point.date);
      return { ...point, real, errorPct: real == null ? null : (point.v - real) / real };
    });
};

export type Scorecard = {
  days: number; mae: number; naiveMae: number; skill: number;
  inBand: number; rightWay: number; worst: SettledPoint;
};

/**
 * Naif referans "fiyat başladığı yerde kalır" kuralıdır (rastgele yürüyüş).
 * Bir modelin değeri ancak bu referanstan iyi olmasıyla ölçülür.
 */
export const buildScorecard = (table: SettledPoint[], basePrice: number): Scorecard | null => {
  const settled = table.filter(row => row.real != null) as (SettledPoint & { real: number })[];
  if (!settled.length) return null;
  const mae = avg(settled.map(row => Math.abs(row.v / row.real - 1)));
  const naiveMae = avg(settled.map(row => Math.abs(basePrice / row.real - 1)));
  return {
    days: settled.length, mae, naiveMae,
    skill: naiveMae > 0 ? 1 - mae / naiveMae : 0,
    inBand: settled.filter(row => row.real >= row.lo && row.real <= row.hi).length,
    rightWay: settled.filter(row => (row.v >= basePrice) === (row.real >= basePrice)).length,
    worst: settled.reduce((a, b) => Math.abs(a.errorPct!) >= Math.abs(b.errorPct!) ? a : b),
  };
};
