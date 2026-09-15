import { describe, expect, it } from 'vitest';
import { DESCRIPTION_MAX, pageDescription, turkishDateTime } from './page';

describe('/yorum sayfası yardımcıları', () => {
  it('tarihi Türkiye saatinde ve Türkçe ay adıyla yazar', () => {
    expect(turkishDateTime('2026-09-15T12:54:39+00:00')).toBe('15 Eylül 2026, 15:54');
    expect(turkishDateTime('2026-09-15T22:30:00Z')).toBe('16 Eylül 2026, 01:30');   // gün UTC+3 ile döner
    expect(turkishDateTime('bozuk')).toBe('');
    expect(turkishDateTime(null)).toBe('');
  });

  it('açıklamayı kelime sınırında keser, kısa özeti olduğu gibi bırakır', () => {
    const uzun = Array(30).fill('Piyasa temkinli.').join(' ');
    const desc = pageDescription(uzun);
    expect(desc.length).toBeLessThanOrEqual(DESCRIPTION_MAX);
    expect(desc.endsWith('…')).toBe(true);
    expect(desc).not.toMatch(/ …$/);
    expect(pageDescription('Kısa   özet.')).toBe('Kısa özet.');
    expect(pageDescription(null)).toContain('yeniden yazılır');
  });
});
