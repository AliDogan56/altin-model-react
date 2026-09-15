import { describe, expect, it } from 'vitest';
import { ageLabel, ageMinutes, isUnread, shouldMarkSeen } from './unread';

describe('yeni yorum kararı', () => {
  it('üretim zamanı son görülenden büyükse yeni; ilk ziyarette ve bozuk damgada da yeni (henüz okunmamış)', () => {
    expect(isUnread('2026-09-15T12:00:00+00:00', '2026-09-15T11:00:00+00:00')).toBe(true);
    expect(isUnread('2026-09-15T12:00:00+00:00', '2026-09-15T12:00:00+00:00')).toBe(false);
    expect(isUnread('2026-09-15T11:00:00+00:00', '2026-09-15T12:00:00+00:00')).toBe(false);
    expect(isUnread('2026-09-15T12:00:00+00:00', null)).toBe(true);
    expect(isUnread('2026-09-15T12:00:00+00:00', 'bozuk')).toBe(true);
    expect(isUnread(null, '2026-09-15T12:00:00+00:00')).toBe(false);
    expect(isUnread('bozuk', '2026-09-15T12:00:00+00:00')).toBe(false);
  });
  it('yaş ve etiket', () => {
    const now = Date.parse('2026-09-15T12:00:00Z');
    expect(ageMinutes('2026-09-15T11:48:00Z', now)).toBe(12);
    expect(ageLabel(0)).toBe('şimdi'); expect(ageLabel(12)).toBe('12 dk'); expect(ageLabel(150)).toBe('2 sa'); expect(ageLabel(3000)).toBe('2 gün'); expect(ageLabel(null)).toBe('');
  });
  it('okundu kuralı: 5 sn açık, dinleme ya da yarıyı geçme', () => {
    expect(shouldMarkSeen({ openMs: 1000, scrolledRatio: 0, listened: false })).toBe(false);
    expect(shouldMarkSeen({ openMs: 5000, scrolledRatio: 0, listened: false })).toBe(true);
    expect(shouldMarkSeen({ openMs: 0, scrolledRatio: 0.5, listened: false })).toBe(true);
    expect(shouldMarkSeen({ openMs: 0, scrolledRatio: 0, listened: true })).toBe(true);
  });
});
