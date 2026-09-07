import { describe, expect, it } from 'vitest';
import { aggregate, bucketKey } from './aggregate';

const mum = (date: string, c: number, h = c + 1, l = c - 1) => ({ date, h, l, c });

describe('bucketKey', () => {
  it('haftayı pazartesiye çeker', () => {
    // 2026-08-26 çarşamba → 2026-08-24 pazartesi
    expect(bucketKey('2026-08-26', 'hafta')).toBe('2026-08-24');
    expect(bucketKey('2026-08-24', 'hafta')).toBe('2026-08-24');
    // pazar aynı haftaya ait olmalı, sonrakine değil
    expect(bucketKey('2026-08-30', 'hafta')).toBe('2026-08-24');
    expect(bucketKey('2026-08-31', 'hafta')).toBe('2026-08-31');
  });

  it('ay, çeyrek ve yarıyıl anahtarları takvimle uyumlu', () => {
    expect(bucketKey('2026-08-26', 'ay')).toBe('2026-08');
    expect(bucketKey('2026-08-26', 'ceyrek')).toBe('2026-C3');
    expect(bucketKey('2026-01-05', 'ceyrek')).toBe('2026-C1');
    expect(bucketKey('2026-06-30', 'yariyil')).toBe('2026-Y1');
    expect(bucketKey('2026-07-01', 'yariyil')).toBe('2026-Y2');
  });
});

describe('aggregate', () => {
  const gunler = [
    mum('2026-08-24', 100, 105, 95),
    mum('2026-08-25', 110, 120, 90),
    mum('2026-08-26', 108, 112, 104),
    mum('2026-08-31', 130, 131, 129),   // sonraki hafta
  ];

  it('günlükte seriyi olduğu gibi bırakır', () => {
    expect(aggregate(gunler, 'gun')).toEqual(gunler);
  });

  it('haftalıkta yüksek/düşük uçları ve son kapanışı alır', () => {
    const hafta = aggregate(gunler, 'hafta');
    expect(hafta).toHaveLength(2);
    expect(hafta[0]).toEqual({ date: '2026-08-24', h: 120, l: 90, c: 108 });
    expect(hafta[1].c).toBe(130);
  });

  it('kova tarihi ilk günün tarihidir', () => {
    expect(aggregate(gunler, 'ay')[0].date).toBe('2026-08-24');
  });

  it('bozuk mumları atlar, kalanı bozmaz', () => {
    const bozuk = [...gunler, { date: '2026-09-01', h: NaN, l: 1, c: 2 }];
    const ay = aggregate(bozuk, 'ay');
    expect(ay.every(c => Number.isFinite(c.h) && Number.isFinite(c.c))).toBe(true);
  });

  it('kaynağı değiştirmez', () => {
    const kopya = gunler.map(c => ({ ...c }));
    aggregate(gunler, 'hafta');
    expect(gunler).toEqual(kopya);
  });

  it('boş seride boş döner', () => {
    expect(aggregate([], 'ay')).toEqual([]);
  });
});
