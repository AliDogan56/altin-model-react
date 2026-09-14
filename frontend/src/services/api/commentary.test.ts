import { describe, expect, it } from 'vitest';
import { parseCommentary } from './commentary';
import { liveSourceLabel } from '../../content/commentary';

const gecerli = {
  version: '20260914T180848Z', as_of: '2026-09-14', generated_at: '2026-09-14T18:08:48+00:00', age_seconds: 120, run_mode: 'full',
  trigger: { reason: 'first_generation', price: 4315.02 },
  live: { price: 4315.02, source: 'PAXG-USD (spot izleyen)', time_utc: '2026-09-14T18:05:38+00:00', change_vs_fix_pct: -1.62, change_vs_fix_usd: -71.23, change_vs_prev_close_pct: -0.48, atr_multiple: -0.9 },
  official_fix: { date: '2026-09-11', price: 4386.25 },
  title: 'Ons Altın Analiz Masası Günlük Raporu', headline: 'Spot altın 4.315 dolar…', summary: 'Özet.',
  sections: [{ id: 'giris', title: 'Piyasaya Bakış', text: 'Metin.' }, { id: 'kapanis', title: 'Sonuç', text: 'Son.' }],
  usage: { anchor: { model: 'gemini/x' } }, durations_seconds: { total: 198.8 }, disclaimer: 'Yatırım tavsiyesi değildir.',
};

describe('parseCommentary', () => {
  it('yanıtı alanlarıyla çevirir; kullanım ve model adları taşınmaz', () => {
    const out = parseCommentary(gecerli)!;
    expect(out.version).toBe('20260914T180848Z');
    expect(out.triggerReason).toBe('first_generation');
    expect(out.live).toEqual({ price: 4315.02, source: 'PAXG-USD (spot izleyen)', timeUtc: '2026-09-14T18:05:38+00:00', changeVsFixPct: -1.62, changeVsFixUsd: -71.23, changeVsPrevClosePct: -0.48 });
    expect(out.officialFix).toEqual({ date: '2026-09-11', price: 4386.25 });
    expect(out.sections).toHaveLength(2);
    expect(JSON.stringify(out)).not.toContain('gemini');
  });
  it('zorunlu alan eksikse ya da bölüm yoksa null', () => {
    expect(parseCommentary(null)).toBeNull();
    expect(parseCommentary({ ...gecerli, headline: 1 })).toBeNull();
    expect(parseCommentary({ ...gecerli, sections: [] })).toBeNull();
    expect(parseCommentary({ ...gecerli, sections: [{ id: 'x' }] })).toBeNull();
  });
  it('bozuk canlı fiyat ve fiks yalnız o alanı düşürür', () => {
    const out = parseCommentary({ ...gecerli, live: { price: 'yok' }, official_fix: null })!;
    expect(out.live).toBeNull(); expect(out.officialFix).toBeNull(); expect(out.sections).toHaveLength(2);
  });
  it('kaynak adı üçüncü taraf adı taşımaz', () => {
    expect(liveSourceLabel('PAXG-USD (spot izleyen)')).toBe('spot izleyen seri');
    expect(liveSourceLabel('GC=F')).toBe('vadeli altın');
    expect(liveSourceLabel('')).toBe('canlı seri');
  });
});
