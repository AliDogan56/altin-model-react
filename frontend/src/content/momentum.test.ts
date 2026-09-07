import { describe, expect, it } from 'vitest';
import { feedNote } from './momentum';

describe('feedNote — gün içi akış notu', () => {
  it('normal akışta not yok', () => {
    expect(feedNote(null)).toBeNull();
    expect(feedNote({ fallback: false, primaryAgeMinutes: 5, stale: false })).toBeNull();
  });
  it('yedeğe düşülünce sessizlik süresi saat olarak yazılır', () => {
    expect(feedNote({ fallback: true, primaryAgeMinutes: 3475, stale: false }))
      .toBe('Vadeli fiyat akışı 58 saattir mum vermiyor; bu okuma spot izleyen bir seriden hesaplandı.');
    expect(feedNote({ fallback: true, primaryAgeMinutes: 90, stale: false })).toContain('1,5 saattir');
  });
  it('yedek de yoksa bayat notu', () => {
    expect(feedNote({ fallback: false, primaryAgeMinutes: 180, stale: true })).toContain('yedek seri de alınamadı');
  });
});
