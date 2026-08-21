import { describe, expect, it } from 'vitest';
import { findLevels } from './supportResistance';

describe('findLevels', () => {
  it('kısa seride boş döner', () => {
    expect(findLevels([1, 2, 3])).toEqual([]);
  });

  it('tekrar eden dönüş bölgelerini tek seviyede kümeler', () => {
    // 100 ve 200 civarında ikişer kez dönen testere dişi seri
    const s: number[] = [];
    for (let i = 0; i < 4; i++) s.push(100, 130, 170, 200, 170, 130);
    const levels = findLevels(s);
    expect(levels.length).toBeGreaterThan(0);
    expect(levels.every(l => l.touches >= 2)).toBe(true);
  });

  it('en fazla dört seviye döner ve dokunuşa göre sıralar', () => {
    const s = Array.from({ length: 120 }, (_, i) => 100 + Math.sin(i / 3) * 30);
    const levels = findLevels(s);
    expect(levels.length).toBeLessThanOrEqual(4);
    for (let i = 1; i < levels.length; i++) expect(levels[i - 1].touches).toBeGreaterThanOrEqual(levels[i].touches);
  });

  it('tek dokunuşluk gürültüyü eler', () => {
    const s = Array.from({ length: 60 }, (_, i) => 100 + i);   // düz artan, dönüş yok
    expect(findLevels(s)).toEqual([]);
  });
});
