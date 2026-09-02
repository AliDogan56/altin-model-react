import { describe, expect, it } from 'vitest';
import { trendLine } from './trend';

describe('trendLine', () => {
  it('sabit yüzde büyümede kusursuz uyum verir', () => {
    // Her adımda %2: log uzayında tam doğru.
    const seri = Array.from({ length: 20 }, (_, i) => 100 * 1.02 ** i);
    const t = trendLine(seri)!;
    expect(t.r2).toBeCloseTo(1, 6);
    expect(t.slopePct).toBeCloseTo(0.02, 6);
    expect(t.direction).toBe('up');
    expect(t.first).toBeCloseTo(100, 6);
  });

  /* Asıl iddia: trend noktaları birleştirmez, genel yönü verir. */
  it('gürültülü seride uçlara değil eğilime uyar', () => {
    const seri = Array.from({ length: 40 }, (_, i) => 100 + i + (i % 2 ? 8 : -8));
    const t = trendLine(seri)!;
    expect(t.direction).toBe('up');
    // Son nokta gürültüyle aşağı sapsa da trend son değeri onu izlemez.
    expect(Math.abs(t.last - seri[seri.length - 1])).toBeGreaterThan(3);
    expect(t.r2).toBeGreaterThan(0.6);   // ±8 gürültüde ölçülen: 0,685
  });

  it('düşen seride yön aşağıdır', () => {
    const t = trendLine(Array.from({ length: 15 }, (_, i) => 200 * 0.97 ** i))!;
    expect(t.direction).toBe('down');
    expect(t.slopePct).toBeLessThan(0);
    expect(t.changePct).toBeLessThan(0);
  });

  /* Sabit seride kayan nokta yüzünden r² 0 çıkıyordu; eşikle düzeltildi. */
  it('yatay seride yön yatay ve uyum tanımlı', () => {
    const t = trendLine(new Array(12).fill(1500))!;
    expect(t.at(5)).toBeCloseTo(1500, 6);
    expect(t.direction).toBe('flat');
    expect(t.slopePct).toBeCloseTo(0, 9);
    expect(t.r2).toBe(1);
  });

  /* Eşik dönem boyu toplam değişime bakar; kova uzunluğundan bağımsızdır.
     Önce adım başına eğime bakılıyordu ve 90 günde -%6,37 olan gerçek seri
     "yatay" çıkıyordu. */
  it('yön eşiği dönem boyu toplam değişimdir', () => {
    // 30 adımda toplam %0,3: yatay.
    const zayif = trendLine(Array.from({ length: 30 }, (_, i) => 100 * 1.0001 ** i))!;
    expect(zayif.changePct).toBeLessThan(0.01);
    expect(zayif.direction).toBe('flat');
    // Aynı adım sayısı, toplam %6 düşüş: aşağı.
    const dusen = trendLine(Array.from({ length: 90 }, (_, i) => 100 * 0.99927 ** i))!;
    expect(dusen.changePct).toBeLessThan(-0.05);
    expect(dusen.direction).toBe('down');
  });

  it('kova uzunluğu değişince yön kararı değişmez', () => {
    // Aynı toplam değişim, farklı nokta sayısı: ikisi de "up".
    const az = trendLine([100, 103, 106])!;
    const cok = trendLine(Array.from({ length: 60 }, (_, i) => 100 * 1.001 ** i))!;
    expect(az.direction).toBe('up');
    expect(cok.direction).toBe('up');
  });

  it('at() uydurulmuş doğruyu verir, veriyi değil', () => {
    const seri = [100, 300, 100, 300, 100, 300];
    const t = trendLine(seri)!;
    expect(t.at(0)).not.toBe(100);
    expect(t.at(0)).toBeCloseTo(t.first, 9);
  });

  it('yetersiz ya da geçersiz veride null döner', () => {
    expect(trendLine([])).toBeNull();
    expect(trendLine([100])).toBeNull();
    expect(trendLine([0, -5, NaN])).toBeNull();
    expect(trendLine([100, NaN, 0])).toBeNull();   // tek geçerli nokta kalır
  });

  it('r2 düşük olduğunda bunu bildirir', () => {
    const t = trendLine([100, 180, 95, 190, 92, 200, 90])!;
    expect(t.r2).toBeLessThan(0.35);
  });
});

describe('regresyon kanalı', () => {
  it('sigma artıkların oransal yayılımıdır', () => {
    // Trend etrafında ±%10 salınan seri: sigma ~0,1 civarında olmalı.
    const seri = Array.from({ length: 40 }, (_, i) => 100 * (i % 2 ? 1.1 : 0.9));
    const t = trendLine(seri)!;
    expect(t.sigma).toBeGreaterThan(0.08);
    expect(t.sigma).toBeLessThan(0.12);
  });

  it('kusursuz uyumda kanal sıfır genişlikte', () => {
    const t = trendLine(Array.from({ length: 20 }, (_, i) => 100 * 1.02 ** i))!;
    expect(t.sigma).toBeCloseTo(0, 9);
    expect(t.band(5, 2)).toBeCloseTo(t.at(5), 6);
  });

  /* Bant log uzayında simetrik, fiyat ekseninde çarpımsaldır: %8 sapma yüksek
     fiyatta daha çok dolar eder ve bant öyle açılmalıdır. */
  it('bant fiyat ekseninde çarpımsal açılır', () => {
    const t = trendLine(Array.from({ length: 30 }, (_, i) => 100 * 1.05 ** i + (i % 3) * 4))!;
    const ustGenislikBas = t.band(0, 1) - t.at(0);
    const ustGenislikSon = t.band(29, 1) - t.at(29);
    expect(ustGenislikSon).toBeGreaterThan(ustGenislikBas);
    // oran ise sabit
    expect(t.band(0, 1) / t.at(0)).toBeCloseTo(t.band(29, 1) / t.at(29), 9);
  });

  it('band(i,0) trend çizgisinin kendisidir', () => {
    const t = trendLine([100, 120, 110, 140, 130])!;
    expect(t.band(3, 0)).toBeCloseTo(t.at(3), 9);
  });

  it('lastZ son gözlemin kanaldaki yerini verir', () => {
    const temiz = Array.from({ length: 30 }, (_, i) => 100 * 1.01 ** i);
    const trendUstunde = trendLine([...temiz.slice(0, 29), temiz[29] * 1.25])!;
    const trendAltinda = trendLine([...temiz.slice(0, 29), temiz[29] * 0.8])!;
    expect(trendUstunde.lastZ).toBeGreaterThan(1);
    expect(trendAltinda.lastZ).toBeLessThan(-1);
  });

  it('yatay seride kanal sıfır ve konum sıfırdır', () => {
    const t = trendLine(new Array(12).fill(2000))!;
    expect(t.sigma).toBe(0);
    expect(t.lastZ).toBe(0);
    // exp(log(2000)) kayan noktada tam 2000 değil; kanal genişliği sıfır olması yeter.
    expect(t.band(4, 2)).toBeCloseTo(2000, 6);
    expect(t.band(4, 2)).toBe(t.at(4));
  });
});
