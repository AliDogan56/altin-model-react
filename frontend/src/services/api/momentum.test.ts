import { describe, expect, it } from 'vitest';
import { parseMomentum } from './momentum';

/* Servis destek/direnç ve kırılım hedefi de döner; arayüz onları kullanmadığı
   için istemci yalnız momentum büyüklüklerini çevirir. Seviyeler panelin
   pivot merdiveninden gelir (`domain/momentum/breakPotential.ts`). */
const gecerli = {
  as_of: '2026-09-01T13:22:20+00:00',
  price: 4415.6, direction: 'DOWN', strength: 77, trend: 'STRENGTHENING',
  support: { level: 'S2', value: 4380.3, distance: 16.9, distance_pct: -0.384,
             distance_sigma: 4.21, sources: ['S2'] },
  breakout: { side: 'support', level: 'S2', value: 4380.3, strength: 'STRONG' },
  components: { velocity: -2.579, rsi: -1.026 },
  session: { bars: 162, remaining_bars: 114, volatility_pct: 0.0888,
             expected_move: 76.94, has_volume: true },
};

describe('parseMomentum', () => {
  it('momentum büyüklüklerini alanlarıyla çevirir', () => {
    const out = parseMomentum(gecerli)!;
    expect(out.direction).toBe('DOWN');
    expect(out.strength).toBe(77);
    expect(out.trend).toBe('STRENGTHENING');
    expect(out.price).toBe(4415.6);
    expect(out.session).toEqual({ bars: 162, remainingBars: 114, volatilityPct: 0.0888,
      expectedMove: 76.94, hasVolume: true });
  });

  /* Bozuk yanıt sayfayı düşürmemeli; bölüm hiç görünmemeli. */
  it('bozuk yanıtı reddeder, fırlatmaz', () => {
    expect(parseMomentum(null)).toBeNull();
    expect(parseMomentum('yanıt değil')).toBeNull();
    expect(parseMomentum({ ...gecerli, price: 'x' })).toBeNull();
    expect(parseMomentum({ ...gecerli, direction: 'SIDEWAYS' })).toBeNull();
    expect(parseMomentum({ ...gecerli, trend: 'FAST' })).toBeNull();
    expect(parseMomentum({ ...gecerli, session: {} })).toBeNull();
  });

  /* Kullanılmayan seviye alanları bozuk gelse de momentum okunabilir olmalı. */
  it('servisin seviye alanları bozuksa yanıt yine ayakta kalır', () => {
    const out = parseMomentum({ ...gecerli, support: 'çöp', breakout: 42,
      resistance: null, ladder: 'dizi değil' })!;
    expect(out).not.toBeNull();
    expect(out.direction).toBe('DOWN');
  });

  it('güç 0-100 aralığına kırpılır', () => {
    expect(parseMomentum({ ...gecerli, strength: 140 })!.strength).toBe(100);
    expect(parseMomentum({ ...gecerli, strength: -5 })!.strength).toBe(0);
    expect(parseMomentum({ ...gecerli, strength: 61.4 })!.strength).toBe(61);
  });

  it('sayı olmayan bileşenler atılır', () => {
    const out = parseMomentum({ ...gecerli, components: { velocity: 1.2, bozuk: 'x' } })!;
    expect(out.components).toEqual({ velocity: 1.2 });
  });

  it('eksik seans sayıları sıfıra düşer, oynaklık zorunludur', () => {
    const out = parseMomentum({ ...gecerli,
      session: { volatility_pct: 0.09 } })!;
    expect(out.session.bars).toBe(0);
    expect(out.session.expectedMove).toBe(0);
    expect(out.session.hasVolume).toBe(false);
  });
});
