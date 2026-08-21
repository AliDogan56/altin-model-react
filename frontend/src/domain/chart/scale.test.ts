import { describe, expect, it } from 'vitest';
import { computeDomain, dropNear, pickTimeTicks } from './scale';

const share = (core: number[], d: { min: number; max: number }) =>
  (Math.max(...core) - Math.min(...core)) / (d.max - d.min);

describe('computeDomain', () => {
  it('bütçeye sığan bant tamamen gösterilir', () => {
    const d = computeDomain([100, 110], [98, 112]);
    expect(d.bandClipped).toBe(false);
    expect(d.min).toBeLessThan(98);
    expect(d.max).toBeGreaterThan(112);
  });

  it('çok geniş bant kırpılır, çekirdeğin payı korunur', () => {
    // çekirdek 10 birim, bant 200 birim: hepsi gösterilse çekirdek %5'e düşerdi
    const core = [100, 110];
    const d = computeDomain(core, [10, 210]);
    expect(d.bandClipped).toBe(true);
    expect(share(core, d)).toBeCloseTo(0.5, 6);
  });

  it('kırpma bandın ihtiyacı yönünde dağıtılır', () => {
    // bant yalnız yukarı taşıyor: aşağıya gereksiz yer açılmamalı
    const d = computeDomain([100, 110], [100, 400]);
    expect(d.bandClipped).toBe(true);
    expect(d.min).toBeGreaterThan(97);
    expect(d.max).toBeGreaterThan(110);
    expect(400 - d.max).toBeGreaterThan(250);      // bandın tepesi gerçekten kırpıldı
  });

  it('pay oranı ayarlanabilir', () => {
    const core = [100, 110];
    expect(share(core, computeDomain(core, [0, 500], 0.8))).toBeCloseTo(0.8, 6);
    expect(share(core, computeDomain(core, [0, 500], 0.3))).toBeCloseTo(0.3, 6);
  });

  it('bant yokken pad her iki yana eşit eklenir', () => {
    const d = computeDomain([100, 200], [], 0.5, 0.1);
    expect(d.min).toBeCloseTo(90, 9);
    expect(d.max).toBeCloseTo(210, 9);
  });

  it('tek değerli seride sıfır yükseklikli aralık üretmez', () => {
    const d = computeDomain([100]);
    expect(d.max).toBeGreaterThan(d.min);
  });

  it('geçersiz değerleri eler, hiç veri yoksa güvenli aralık verir', () => {
    const d = computeDomain([NaN, 100, Infinity, 120]);
    expect(d.min).toBeLessThan(100);
    expect(d.max).toBeGreaterThan(120);
    expect(computeDomain([])).toEqual({ min: 0, max: 1, bandClipped: false });
  });
});

describe('pickTimeTicks', () => {
  it('uçları dahil eder ve istenen sayıda üretir', () => {
    expect(pickTimeTicks(-90, 90, 5)).toEqual([-90, -45, 0, 45, 90]);
  });
  it('dar aralıkta tekrarları eler', () => {
    expect(pickTimeTicks(0, 2, 6)).toEqual([0, 1, 2]);
  });
  it('geçersiz aralıkta boş döner', () => {
    expect(pickTimeTicks(5, 5, 4)).toEqual([]);
    expect(pickTimeTicks(0, 10, 1)).toEqual([]);
  });
});

describe('dropNear', () => {
  it('bugüne çok yakın etiketleri atar', () => {
    expect(dropNear([-90, -8, 0, 6, 90], 0, 10)).toEqual([-90, 90]);
  });
});
