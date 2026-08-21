import { describe, expect, it } from 'vitest';
import { asOf, parseCsv, shiftDays } from './series';

const csv = `observation_date,DGS10
2026-08-10,4.10
2026-08-11,.
2026-08-12,4.25`;

describe('parseCsv', () => {
  it('başlığı atlar ve eksik değerleri eler', () => {
    expect(parseCsv(csv)).toEqual([
      { date: '2026-08-10', value: 4.1 },
      { date: '2026-08-12', value: 4.25 },
    ]);
  });
});

describe('asOf', () => {
  const rows = parseCsv(csv);
  it('o güne ait değer yoksa önceki en yakını verir', () => {
    // "5 gözlem önce" değil "5 takvim günü önce" okunmalı.
    expect(asOf(rows, '2026-08-11')).toBe(4.1);
    expect(asOf(rows, '2026-08-13')).toBe(4.25);
  });
  it('serinin başından önce null döner', () => {
    expect(asOf(rows, '2026-08-01')).toBeNull();
  });
});

describe('shiftDays', () => {
  it('ay ve yıl sınırını geriye doğru geçer', () => {
    expect(shiftDays('2026-09-01', 1)).toBe('2026-08-31');
    expect(shiftDays('2027-01-01', 1)).toBe('2026-12-31');
    expect(shiftDays('2026-08-20', 20)).toBe('2026-07-31');
  });
});
