import { describe, expect, it } from 'vitest';
import { GRAMS_PER_OUNCE, buildZiynetRows, pureGramPrice } from './ziynet';

const quote = (satis: number, alis: number) =>
  ({ satis, alis, dir: '', low: 0, high: 0, prev: 0, time: '12:00' });

const quotes = {
  ALTIN: quote(7091, 7052),
  CEYREK_YENI: quote(11592, 11460),
  ATA_YENI: quote(47034, 46476),
};

describe('pureGramPrice', () => {
  it('ons fiyatını gram TL karşılığına çevirir', () => {
    expect(pureGramPrice(4605.5, 48.1)).toBeCloseTo(4605.5 * 48.1 / GRAMS_PER_OUNCE, 9);
  });
  it('kur veya ons yoksa null döner', () => {
    expect(pureGramPrice(0, 48)).toBeNull();
    expect(pureGramPrice(4600, 0)).toBeNull();
  });
});

describe('buildZiynetRows', () => {
  it('ürünün saf altın gramını uygular', () => {
    const rows = buildZiynetRows(quotes, 4605.5, 48.1);
    const ceyrek = rows.find(r => r.code === 'CEYREK_YENI')!;
    expect(ceyrek.pureGrams).toBeCloseTo(1.75 * 0.916, 9);
    expect(ceyrek.rawValue).toBeCloseTo(pureGramPrice(4605.5, 48.1)! * 1.75 * 0.916, 6);
  });

  /* Gerçek kotasyonlarla ölçüldü: gram ≈ %0, ziynet ürünleri %1–2 işçilik taşır. */
  it('işçilik payı gerçekçi aralıkta çıkar', () => {
    const rows = buildZiynetRows(quotes, 4605.5, 48.1);
    const gram = rows.find(r => r.code === 'ALTIN')!;
    const ceyrek = rows.find(r => r.code === 'CEYREK_YENI')!;
    expect(gram.premium!).toBeGreaterThan(-0.01);
    expect(gram.premium!).toBeLessThan(0.01);
    expect(ceyrek.premium!).toBeGreaterThan(0.005);
    expect(ceyrek.premium!).toBeLessThan(0.04);
  });

  it('kur gelmeden ham değer ve prim gösterilmez, fiyat yine de listelenir', () => {
    const rows = buildZiynetRows(quotes, 4605.5, 0);
    expect(rows).toHaveLength(3);
    expect(rows[0].rawValue).toBeNull();
    expect(rows[0].premium).toBeNull();
    expect(rows[0].satis).toBe(7091);
  });

  it('makas oranı satışa göre hesaplanır', () => {
    const rows = buildZiynetRows(quotes, 4605.5, 48.1);
    expect(rows[0].spreadPct).toBeCloseTo((7091 - 7052) / 7091, 12);
  });

  it('tanımsız ürün kodu atlanır, sıra korunur', () => {
    const rows = buildZiynetRows({ ...quotes, BILINMEYEN: quote(1, 1) }, 4605.5, 48.1,
      ['CEYREK_YENI', 'BILINMEYEN', 'ALTIN']);
    expect(rows.map(r => r.code)).toEqual(['CEYREK_YENI', 'ALTIN']);
  });

  it('kaynağın aralık doğrulaması korunur', () => {
    const rows = buildZiynetRows({ ALTIN: { ...quote(7091, 7052), low: 5, high: 7132 } }, 4605.5, 48.1);
    expect(rows[0].hasRange).toBe(false);
  });
});
