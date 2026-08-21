import type { Forecast, ModelArtifact } from './model/types';
import { buildDailyPath } from './model/predict';

/** Aylık ödemeyle toplam getirinin başa baş geldiği faiz; ikili arama ile bulunur. */
export const breakEvenLoanRate = (totalReturn: number, months: number): number | null => {
  if (!Number.isFinite(totalReturn) || totalReturn <= 0) return null;
  const target = 1 + totalReturn;
  const totalRatio = (rate: number) => rate === 0 ? 1 : months * (rate * (1 + rate) ** months / ((1 + rate) ** months - 1));
  let lo = 0, hi = 1;
  if (totalRatio(hi) < target) return hi;
  for (let i = 0; i < 80; i++) { const mid = (lo + hi) / 2; if (totalRatio(mid) < target) lo = mid; else hi = mid; }
  return (lo + hi) / 2;
};

export const loanPayment = (principal: number, monthlyRate: number, months: number): number => {
  const rate = Math.max(0, monthlyRate);
  return rate === 0 ? principal / months : principal * (rate * (1 + rate) ** months / ((1 + rate) ** months - 1));
};

export type LoanScenario = { label: string; ret: number; tone: string; monthly: number | null };

/** 180 günü aşan vadeler modelin en uzun ufkundan türetilir; `derived` bunu işaretler. */
export const loanProjection = (model: ModelArtifact, forecast: Forecast, months: number) => {
  const days = months * 30;
  const path = buildDailyPath(model, forecast, Math.min(days, 180));
  const last = path.at(-1)!;
  let mean = last.ret, err = last.err, derived = false;
  if (days > 180) {
    const scale = days / 180;
    mean = Math.expm1(Math.log1p(Math.max(-0.95, mean)) * scale);
    err *= Math.sqrt(scale);
    derived = true;
  }
  const scenarios: LoanScenario[] = [
    { label: 'Alt bant', ret: mean - err, tone: 'low' },
    { label: 'Model tahmini', ret: mean, tone: 'base' },
    { label: 'Üst bant', ret: mean + err, tone: 'high' },
  ].map(s => ({ ...s, monthly: breakEvenLoanRate(s.ret, months) }));
  return { months, derived, scenarios };
};

export type LoanCostInput = {
  amount: number; ratePct: number; months: number;
  currentFx: number; futureFx: number;
  scenarios: LoanScenario[];
};

/** Kredi maliyeti TL, altın getirisi USD cinsindendir; ikisi ancak kur beklentisi
 *  üzerinden aynı para birimine getirildiğinde karşılaştırılabilir. */
export const loanCosts = ({ amount, ratePct, months, currentFx, futureFx, scenarios }: LoanCostInput) => {
  const principal = Math.max(0, amount || 0);
  const monthly = loanPayment(principal, Math.max(0, ratePct || 0) / 100, months);
  const total = monthly * months;
  const targetFx = futureFx || currentFx;
  const fxReturn = currentFx > 0 ? targetFx / currentFx - 1 : 0;
  const results = scenarios.map(s => {
    const tlReturn = (1 + s.ret) * (1 + fxReturn) - 1;
    return {
      ...s, onsReturn: s.ret, tlReturn,
      monthly: breakEvenLoanRate(tlReturn, months),
      endValue: principal * (1 + tlReturn),
      net: principal * (1 + tlReturn) - total,
    };
  });
  return { monthly, total, currentFx, targetFx, fxReturn, results };
};
