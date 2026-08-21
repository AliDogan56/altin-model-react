import { describe, expect, it } from 'vitest';
import { goldFeatures } from './goldFeatures';
import { macroFeatures } from './macroFeatures';
import type { SeriesPoint } from '../../lib/series';

const flat = (n: number, v: number) => Array.from({ length: n }, () => v);

describe('goldFeatures', () => {
  it('yatay seride getiri ve oynaklık sıfırdır', () => {
    const close = flat(220, 100);
    const f = goldFeatures({ close, high: close, low: close, volume: flat(220, 1000) });
    expect(f.gold_return_20d).toBe(0);
    expect(f.gold_ma_ratio_200d).toBe(0);
    expect(f.gold_volatility_20d).toBe(0);
    // Tam yatay seride hem kazanç hem kayıp 0; formül 50 değil 0 verir.
    // Gerçek seride oluşmaz, üretimdeki davranış bu; kayıt altına alıyoruz.
    expect(f.gold_rsi14).toBe(0);
  });

  it('sürekli yükselişte RSI üst sınıra dayanır', () => {
    const close = Array.from({ length: 220 }, (_, i) => 100 + i);
    const f = goldFeatures({ close, high: close, low: close, volume: flat(220, 1000) });
    expect(f.gold_rsi14).toBeCloseTo(100, 6);
    expect(f.gold_return_20d).toBeGreaterThan(0);
    expect(f.gold_ma_ratio_20d).toBeGreaterThan(0);
  });

  it('ATR yüzdesi son fiyata oranlıdır', () => {
    const close = flat(220, 200);
    const f = goldFeatures({ close, high: flat(220, 202), low: flat(220, 198), volume: flat(220, 1000) });
    expect(f.gold_atr14_pct).toBeCloseTo(4 / 200, 6);
  });
});

describe('macroFeatures', () => {
  // yoy 12 gözlem geriye bakar: aylık serilerde tam bir yıl.
  const monthly = (vals: number[]): SeriesPoint[] =>
    vals.map((value, i) => ({ date: `2025-${String(i + 1).padStart(2, '0')}-01`, value }));

  const base = () => {
    const s: Record<string, SeriesPoint[]> = {};
    ['DGS10', 'DGS2', 'DFII10', 'DTWEXBGS', 'DCOILWTICO', 'VIXCLS', 'FEDFUNDS', 'UNRATE',
     'CPIAUCSL', 'CPILFESL', 'PPIACO', 'PCEPI', 'PAYEMS', 'RSAFS']
      .forEach(id => { s[id] = monthly(flat(13, 100)); });
    return s;
  };

  it('sabit seride yıllık değişim sıfırdır', () => {
    const f = macroFeatures(base());
    expect(f.CPIAUCSL_yoy_pct).toBe(0);
    expect(f.real_yield_change_5d).toBe(0);
    expect(f.DGS10).toBe(100);
  });

  it('yıllık enflasyonu 12 gözlem geriden ölçer', () => {
    const s = base();
    s.CPIAUCSL = monthly([100, ...flat(11, 100), 103]); // 13. gözlem
    expect(macroFeatures(s).CPIAUCSL_yoy_pct).toBeCloseTo(3, 6);
  });

  it('dolar getirisi oran, faiz değişimi puan cinsindendir', () => {
    const s = base();
    s.DTWEXBGS = monthly([100, 100, 100, 100, 100, 100, 100, 110, 110, 110, 110, 110, 110]);
    s.DFII10 = monthly([2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3]);
    const f = macroFeatures(s);
    expect(f.dollar_return_5d).toBeCloseTo(0, 6);  // son 5 gözlemde değişim yok
    expect(f.DFII10).toBe(3);
    s.DFII10 = monthly([2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 4]);
    // 5 gözlem geri = index 7 (=2), son = 4 -> +2 puan
    expect(macroFeatures(s).real_yield_change_5d).toBeCloseTo(2, 6);
  });
});
