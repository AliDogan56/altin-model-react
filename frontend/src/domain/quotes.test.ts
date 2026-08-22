import { describe, expect, it } from 'vitest';
import { readQuote } from './quotes';

const base = { alis: 7072, satis: 7109, dir: '', low: 6941, high: 7132, prev: 7050, time: '12:00' };

describe('readQuote', () => {
  it('tutarlı kotasyonda aralık ve yüzde gösterilir', () => {
    const q = readQuote(base);
    expect(q.hasRange).toBe(true);
    expect(q.change).toBeCloseTo(7109 / 7050 - 1, 9);
    expect(q.at).toBeGreaterThan(0);
    expect(q.at).toBeLessThanOrEqual(100);
  });

  /* Harem çeyrek/yarım/tam için gün düşüğünü ₺5–₺20 olarak bildiriyor;
     aralık çubuğu anlamsızlaşıyor ve bozuk düşük, yüzde kontrolünün
     toleransını da şişirip yanlış yüzdeyi geçiriyordu. */
  it('gün düşüğü fiyatla kıyaslanamayacak kadar küçükse aralık kullanılmaz', () => {
    const q = readQuote({ ...base, low: 5, high: 11660, satis: 11622, alis: 11493, prev: 10903 });
    expect(q.hasRange).toBe(false);
    expect(q.change).toBeNull();
  });

  it('satış fiyatı aralığın dışındaysa aralık kullanılmaz', () => {
    expect(readQuote({ ...base, satis: 9000 }).hasRange).toBe(false);
  });

  /* Gram: satış 7109, %6,2 artış iddiası önceki kapanışı 6693'e koyuyor —
     günün düşüğü 6941'in belirgin altında, yani kapanış bayat. */
  it('önceki kapanış gün aralığından belirgin uzaksa yüzde gösterilmez', () => {
    expect(readQuote({ ...base, prev: 6693 }).change).toBeNull();
    expect(readQuote({ ...base, prev: 7500 }).change).toBeNull();
  });

  it('makul aşağı boşlukla açılışı kabul eder', () => {
    // bant 191; düşüğün yarım bant altı hâlâ geçerli
    expect(readQuote({ ...base, prev: 6870 }).change).not.toBeNull();
  });

  it('eksik veya sıfır kapanışta yüzde yok', () => {
    expect(readQuote({ ...base, prev: 0 }).change).toBeNull();
  });

  it('makas her zaman hesaplanır', () => {
    expect(readQuote(base).spread).toBe(7109 - 7072);
  });
});
