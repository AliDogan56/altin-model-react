import { resolveHorizon } from './model/horizon';
import type { Forecast } from './model/types';

const DAYS_IN_MONTH = 30;

/** Aylık oranın, gerçek gün sayısına karşılık gelen dönem maliyeti. */
export const periodCostRate = (monthlyRatePct: number, days: number): number => {
  const monthly = Math.max(0, monthlyRatePct || 0) / 100;
  if (days <= 0) return 0;
  return (1 + monthly) ** (days / DAYS_IN_MONTH) - 1;
};

/**
 * Dönem getirisini karşılayan aylık finansman oranı.
 *
 * Önceden taksitli kredi (annüite) formülü kullanılıyordu; oysa 7–30 günlük tek
 * dönemde taksit yok. Getiri pozitif değilse başa baş oran **yoktur** — eski kart
 * bu durumda `%0,00` yazıyor ve "faizsiz kredi başa baş" gibi okunuyordu.
 */
export const breakEvenMonthlyRate = (totalReturn: number, days: number): number | null => {
  if (!Number.isFinite(totalReturn) || totalReturn <= 0 || days <= 0) return null;
  return (1 + totalReturn) ** (DAYS_IN_MONTH / days) - 1;
};

export type LoanScenario = { label: string; ret: number; tone: string };

/**
 * Senaryolar doğrudan modelin **kendi ufkundan** gelir.
 *
 * Kart 3/6/9 ay sunuyor, `loanProjection` ise 30 günlük tahmini `days/30` kadar
 * üstel olarak uzatıyordu: 9 aylık bant ±%32'ye çıkıyor ve modelin hiç ölçülmediği
 * bir vade için sayı üretiliyordu. Artık yalnız 7/14/30 gün.
 */
export const loanProjection = (forecast: Forecast, requestedDays: number) => {
  const { index, horizon } = resolveHorizon(forecast.horizons, requestedDays);
  const mean = forecast.mean[index], err = forecast.err[index];
  const scenarios: LoanScenario[] = [
    { label: 'Alt bant', ret: mean - err, tone: 'low' },
    { label: 'Model tahmini', ret: mean, tone: 'base' },
    { label: 'Üst bant', ret: mean + err, tone: 'high' },
  ];
  return { days: horizon, scenarios };
};

export type LoanCostInput = {
  amount: number; ratePct: number; days: number;
  currentFx: number; futureFx: number;
  scenarios: LoanScenario[];
};

/** Kredi maliyeti TL, altın getirisi USD cinsindendir; ikisi ancak kur beklentisi
 *  üzerinden aynı para birimine getirildiğinde karşılaştırılabilir. */
export const loanCosts = ({ amount, ratePct, days, currentFx, futureFx, scenarios }: LoanCostInput) => {
  const principal = Math.max(0, amount || 0);
  const costRate = periodCostRate(ratePct, days);
  const total = principal * costRate;
  const targetFx = futureFx || currentFx;
  const fxReturn = currentFx > 0 ? targetFx / currentFx - 1 : 0;
  const results = scenarios.map(s => {
    const tlReturn = (1 + s.ret) * (1 + fxReturn) - 1;
    return {
      ...s, onsReturn: s.ret, tlReturn,
      monthly: breakEvenMonthlyRate(tlReturn, days),
      endValue: principal * (1 + tlReturn),
      net: principal * (1 + tlReturn) - principal - total,
    };
  });
  return { costRate, total, currentFx, targetFx, fxReturn, results };
};
