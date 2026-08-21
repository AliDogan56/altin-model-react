import { describe, expect, it } from 'vitest';
import { longDate, pct, pct2, points, shortDate, signedPct2, tryAmount } from './format';

describe('biçimlendirme', () => {
  it('pct tek, pct2 iki ondalık gösterir', () => {
    // %0,71 ile %0,74 tek ondalıkta aynı görünüp kartı kendisiyle çelişkiye düşürmüştü.
    expect(pct(0.0071)).toBe(pct(0.0074));
    expect(pct2(0.0071)).not.toBe(pct2(0.0074));
    expect(pct2(0.0071)).toContain('0,71');
  });

  it('signedPct2 işareti korur ve Türkçe ayraç kullanır', () => {
    expect(signedPct2(0.0133)).toBe('+1,33%');
    expect(signedPct2(-0.0133)).toBe('-1,33%');
  });

  it('points puan sonekiyle işaretli yazar', () => {
    expect(points(1.5)).toBe('+1.50 puan');
    expect(points(-1.5)).toBe('-1.50 puan');
  });

  it('tryAmount negatif ve geçersiz girdiyi sıfırlar', () => {
    expect(tryAmount(-5)).toBe('0');
    expect(tryAmount('abc')).toBe('0');
  });
});

describe('tarih biçimleri', () => {
  it('kısa biçim gün.ay, uzun biçim yıl içerir', () => {
    expect(shortDate('2026-08-14')).toBe('14.08');
    expect(shortDate('2026-08-14', true)).toBe('14.08.26');
    expect(longDate('2026-08-14')).toContain('2026');
  });

  it('ISO tarihi yerel saat diliminde gün kaydırmaz', () => {
    // 'T00:00:00' olmadan UTC olarak ayrıştırılıp bir gün geri gidiyordu.
    expect(shortDate('2026-01-01')).toBe('01.01');
  });
});
