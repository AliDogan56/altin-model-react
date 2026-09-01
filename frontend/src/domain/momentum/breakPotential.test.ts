import { describe, expect, it } from 'vitest';
import { breakPotential, momentumTarget, touchingLevel } from './breakPotential';

/* Momentum servisinin kendi hesabıyla aynı formül; fark yalnız girdinin
   dolar değil oran olması. Böylece spot/vadeli seviye farkı sadeleşir. */
describe('breakPotential', () => {
  it('ulaşılabilir seviye + yüksek momentum = GÜÇLÜ', () => {
    // Beklenen hareket %1,3, seviye %0,6 uzakta: rahat ulaşılır.
    const out = breakPotential(4436.3, 4415.6, 0.013, 82)!;
    expect(out.reach).toBeGreaterThan(1);
    expect(out.strength).toBe('STRONG');
  });

  it('seviyeye ulaşılsa da momentum yoksa ZAYIF', () => {
    const out = breakPotential(4400, 4398, 0.013, 3)!;
    expect(out.reach).toBeGreaterThan(1);   // seviye çok yakın
    expect(out.strength).toBe('WEAK');      // ama kıracak güç yok
  });

  it('uzak seviyede güçlü momentum bile yetmez', () => {
    const yakin = breakPotential(4420, 4400, 0.005, 90)!;
    const uzak = breakPotential(4700, 4400, 0.005, 90)!;
    expect(uzak.score).toBeLessThan(yakin.score);
    expect(uzak.strength).toBe('WEAK');
  });

  /* Asıl mesele: kart Harem spotundan, momentum Yahoo vadelisinden besleniyor
     ve aradaki ~%1 seviye farkı dolar hesabına sızıyordu. */
  it('fiyat çerçevesi ötelenince sonuç değişmez', () => {
    const spot = breakPotential(4398, 4374, 0.013, 60)!;
    const k = 1.0095;                                  // vadeli ~%0,95 yukarıda
    const vadeli = breakPotential(4398 * k, 4374 * k, 0.013, 60)!;
    expect(vadeli.score).toBeCloseTo(spot.score, 10);
    expect(vadeli.strength).toBe(spot.strength);
  });

  it('ulaşma oranı 1de doyurulur: daha yakın olmak skoru şişirmez', () => {
    const yakin = breakPotential(4400.4, 4400, 0.013, 50)!;
    const cokYakin = breakPotential(4400.04, 4400, 0.013, 50)!;
    expect(cokYakin.score).toBeCloseTo(yakin.score, 10);
  });

  it('bozuk girdi null döner, hesap uydurmaz', () => {
    expect(breakPotential(NaN, 4400, 0.01, 50)).toBeNull();
    expect(breakPotential(4400, 0, 0.01, 50)).toBeNull();
    expect(breakPotential(4400, 4400, 0.01, 50)).toBeNull();   // uzaklık sıfır
    expect(breakPotential(4420, 4400, 0, 50)).toBeNull();
    expect(breakPotential(4420, 4400, 0.01, NaN)).toBeNull();
  });
});

describe('momentumTarget', () => {
  const destek = { name: 'S3', value: 4315, above: false };
  const direnc = { name: 'S2', value: 4398, above: true };

  it('yukarı yönlüyse ilk direnci, aşağı yönlüyse ilk desteği hedefler', () => {
    expect(momentumTarget('UP', destek, direnc)).toEqual({ side: 'resistance', level: direnc });
    expect(momentumTarget('DOWN', destek, direnc)).toEqual({ side: 'support', level: destek });
  });

  /* Yön belirsizken "şu seviyeyi kırar" demek uydurma olur. */
  it('yönsüzken hedef vermez', () => {
    expect(momentumTarget('NEUTRAL', destek, direnc)).toBeNull();
  });

  it('o yönde seviye yoksa hedef vermez', () => {
    expect(momentumTarget('UP', destek, null)).toBeNull();
    expect(momentumTarget('DOWN', undefined, direnc)).toBeNull();
  });
});

describe('touchingLevel', () => {
  const merdiven = [
    { name: 'R1', value: 4460, above: true },
    { name: 'S2', value: 4398, above: true },
    { name: 'S3', value: 4315, above: false },
  ];

  it('gürültü içindeki seviyeyi bulur', () => {
    // Mum sigması %0,09 → marj ~%0,18. 4398 fiyattan %0,05 uzakta.
    expect(touchingLevel(merdiven, 4396, 0.09)?.name).toBe('S2');
  });

  it('marj dışındaki seviyeyi temas saymaz', () => {
    expect(touchingLevel(merdiven, 4370, 0.09)).toBeNull();
  });

  it('birden fazla seviye marj içindeyse en yakını seçilir', () => {
    const sik = [{ name: 'A', value: 4400, above: true },
                 { name: 'B', value: 4396.5, above: false }];
    expect(touchingLevel(sik, 4396, 0.5)?.name).toBe('B');
  });

  it('oynaklık okunamazsa temas iddia etmez', () => {
    expect(touchingLevel(merdiven, 4396, 0)).toBeNull();
    expect(touchingLevel(merdiven, 0, 0.09)).toBeNull();
  });
});
