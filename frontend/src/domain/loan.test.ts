import { describe, expect, it } from 'vitest';
import { breakEvenLoanRate, loanCosts, loanPayment } from './loan';

describe('loanPayment', () => {
  it('faizsizde anaparayı vadeye böler', () => {
    expect(loanPayment(1200, 0, 12)).toBe(100);
  });
  it('negatif faizi sıfır kabul eder', () => {
    expect(loanPayment(1200, -0.5, 12)).toBe(100);
  });
  it('faiz arttıkça taksit büyür', () => {
    expect(loanPayment(1000, 0.05, 12)).toBeGreaterThan(loanPayment(1000, 0.02, 12));
  });
});

describe('breakEvenLoanRate', () => {
  it('getiri yoksa oran üretmez', () => {
    expect(breakEvenLoanRate(0, 6)).toBeNull();
    expect(breakEvenLoanRate(-0.1, 6)).toBeNull();
    expect(breakEvenLoanRate(NaN, 6)).toBeNull();
  });

  it('bulunan oran gerçekten başa baş noktasıdır', () => {
    // Tanım: aylık ödeme toplamı / anapara = 1 + getiri
    const months = 9, ret = 0.18;
    const rate = breakEvenLoanRate(ret, months)!;
    const total = loanPayment(1, rate, months) * months;
    expect(total).toBeCloseTo(1 + ret, 6);
  });

  it('getiri büyüdükçe başa baş oranı da büyür', () => {
    expect(breakEvenLoanRate(0.3, 6)!).toBeGreaterThan(breakEvenLoanRate(0.1, 6)!);
  });
});

describe('loanCosts', () => {
  const scenarios = [{ label: 'Baz', ret: 0.10, tone: 'ok', monthly: null }];

  it('kur sabitse TL getirisi ons getirisine eşittir', () => {
    const r = loanCosts({ amount: 100_000, ratePct: 4, months: 6, currentFx: 40, futureFx: 40, scenarios });
    expect(r.fxReturn).toBe(0);
    expect(r.results[0].tlReturn).toBeCloseTo(0.10, 12);
  });

  it('kur artışı ons getirisiyle bileşik çalışır', () => {
    const r = loanCosts({ amount: 100_000, ratePct: 4, months: 6, currentFx: 40, futureFx: 44, scenarios });
    expect(r.fxReturn).toBeCloseTo(0.1, 12);
    expect(r.results[0].tlReturn).toBeCloseTo(1.1 * 1.1 - 1, 12); // toplama değil çarpma
  });

  it('net kâr, vade sonu değerinden toplam ödemeyi düşer', () => {
    const r = loanCosts({ amount: 100_000, ratePct: 4, months: 6, currentFx: 40, futureFx: 40, scenarios });
    expect(r.results[0].net).toBeCloseTo(r.results[0].endValue - r.total, 6);
    expect(r.total).toBeCloseTo(r.monthly * 6, 6);
  });

  it('kur bilinmiyorsa (0) getiriyi bozmaz', () => {
    const r = loanCosts({ amount: 1000, ratePct: 0, months: 6, currentFx: 0, futureFx: 0, scenarios });
    expect(r.fxReturn).toBe(0);
  });
});
