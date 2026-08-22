import { describe, expect, it } from 'vitest';
import { breakEvenMonthlyRate, loanCosts, loanProjection, periodCostRate } from './loan';

const forecast = { horizons: [7, 14, 30], mean: [0.006, 0.001, 0.008],
  err: [0.055, 0.076, 0.106], features: {}, price: 4600 };

describe('periodCostRate', () => {
  it('30 günde aylık oranın kendisidir', () => {
    expect(periodCostRate(4.25, 30)).toBeCloseTo(0.0425, 12);
  });
  it('kısa vadede oransal olarak azalır', () => {
    expect(periodCostRate(4.25, 7)).toBeLessThan(0.0425);
    expect(periodCostRate(4.25, 7)).toBeGreaterThan(0);
  });
  it('negatif oranı ve sıfır günü güvenle karşılar', () => {
    expect(periodCostRate(-5, 30)).toBe(0);
    expect(periodCostRate(4.25, 0)).toBe(0);
  });
});

describe('breakEvenMonthlyRate', () => {
  it('30 günlük dönemde getirinin kendisidir', () => {
    expect(breakEvenMonthlyRate(0.05, 30)).toBeCloseTo(0.05, 12);
  });

  it('bulunan oran gerçekten başa baş noktasıdır', () => {
    const rate = breakEvenMonthlyRate(0.03, 14)!;
    expect(periodCostRate(rate * 100, 14)).toBeCloseTo(0.03, 9);
  });

  /* Eski kart negatif senaryoda "%0,00" yazıyordu; bu "faizsiz kredi başa baş"
     diye okunuyor, oysa hiçbir maliyet düzeyi zararı karşılamaz. */
  it('getiri pozitif değilse başa baş oran yoktur', () => {
    expect(breakEvenMonthlyRate(-0.21, 30)).toBeNull();
    expect(breakEvenMonthlyRate(0, 30)).toBeNull();
  });
});

describe('loanProjection', () => {
  it('senaryolar modelin kendi ufkundan gelir, uzatılmaz', () => {
    const p = loanProjection(forecast, 30);
    expect(p.days).toBe(30);
    expect(p.scenarios.map(s => s.ret)).toEqual([0.008 - 0.106, 0.008, 0.008 + 0.106]);
  });

  it('listede olmayan vade en yakın ufka düşer ve bunu bildirir', () => {
    expect(loanProjection(forecast, 180).days).toBe(30);
    expect(loanProjection(forecast, 10).days).toBe(7);
  });
});

describe('loanCosts', () => {
  const base = { amount: 100000, ratePct: 4.25, days: 30, currentFx: 48, futureFx: 0 };

  it('kur varsayımı yoksa TL getirisi ons getirisine eşittir', () => {
    const r = loanCosts({ ...base, scenarios: loanProjection(forecast, 30).scenarios });
    expect(r.fxReturn).toBe(0);
    expect(r.results[1].tlReturn).toBeCloseTo(0.008, 12);
  });

  it('kur beklentisi TL getirisine bileşik olarak girer', () => {
    const r = loanCosts({ ...base, futureFx: 52.8, scenarios: loanProjection(forecast, 30).scenarios });
    expect(r.fxReturn).toBeCloseTo(0.1, 9);
    expect(r.results[1].tlReturn).toBeCloseTo(1.008 * 1.1 - 1, 9);
  });

  it('net, TL kazancından dönem maliyetinin düşülmüş hâlidir', () => {
    const r = loanCosts({ ...base, scenarios: loanProjection(forecast, 30).scenarios });
    const s = r.results[1];
    expect(s.net).toBeCloseTo(100000 * s.tlReturn - r.total, 6);
  });

  it('toplam maliyet anaparanın dönem oranı kadarıdır', () => {
    const r = loanCosts({ ...base, scenarios: [] });
    expect(r.total).toBeCloseTo(100000 * 0.0425, 6);
  });

  it('kur bilinmiyorsa oran sıfır kabul edilir, bölme hatası olmaz', () => {
    const r = loanCosts({ ...base, currentFx: 0, scenarios: loanProjection(forecast, 30).scenarios });
    expect(Number.isFinite(r.results[0].net)).toBe(true);
  });
});
