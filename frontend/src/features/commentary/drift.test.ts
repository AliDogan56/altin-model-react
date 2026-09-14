import { describe, expect, it } from 'vitest';
import { driftSinceGeneration } from './drift';

describe('driftSinceGeneration', () => {
  it('canlı ile üretim fiyatı arasındaki farkı yüzde ve dolar olarak verir', () => {
    const d = driftSinceGeneration(4302.2, 4311.17)!;
    expect(d.usd).toBeCloseTo(-8.97, 2); expect(d.pct).toBeCloseTo(-0.208, 3); expect(d.beyondTrigger).toBe(false);
  });
  it('%0,5 ve üstü yeniden yazma eşiğini aşar', () => {
    expect(driftSinceGeneration(4333, 4311.17)!.beyondTrigger).toBe(true);
    expect(driftSinceGeneration(4289, 4311.17)!.beyondTrigger).toBe(true);
  });
  it('fiyat yoksa null', () => {
    expect(driftSinceGeneration(null, 4311)).toBeNull();
    expect(driftSinceGeneration(4300, 0)).toBeNull();
  });
});
