/**
 * Seçilen dönemin genel yönü — noktaları birleştiren çizgi değil, **regresyon**.
 *
 * Hesap fiyatın kendisi üzerinde değil **logaritması** üzerinde yapılır. Altın
 * gibi çok yıllık serilerde sabit yüzde büyüme, fiyat ekseninde eğri bir çizgi
 * üretir; log uzayında düz olur. Böylece trend "günde şu kadar dolar" değil
 * "dönem başına şu kadar yüzde" olarak okunur ve serinin başı ile sonu eşit
 * ağırlık taşır.
 */
export type Trend = {
  /** Dönem başına oransal değişim (0,004 = %0,4). */
  slopePct: number;
  /** Uydurulan doğrunun ilk ve son noktadaki fiyat karşılığı. */
  first: number;
  last: number;
  /** Uyum iyiliği, 0–1. Düşükse "genel yön" zayıf demektir. */
  r2: number;
  /** i. noktadaki uydurulmuş fiyat. */
  at: (index: number) => number;
  /** Trendin baştan sona toplam değişimi. */
  changePct: number;
  direction: 'up' | 'down' | 'flat';
  /**
   * Artıkların standart sapması — **log uzayında**, yani oransal. 0,086
   * "trend etrafında tipik sapma %8,6" demektir. Kanal genişliği budur.
   */
  sigma: number;
  /** i. noktada trendin k sigma üstü/altı. k negatif olabilir. */
  band: (index: number, k: number) => number;
  /** Son gözlemin trende göre konumu, sigma cinsinden. */
  lastZ: number;
};

/**
 * Yönün "yatay" sayıldığı eşik: **dönem boyu toplam** değişim yüzde birin altı.
 *
 * Eşik önce adım başına eğime bakıyordu ve kova uzunluğu değiştikçe anlamı
 * kayıyordu: günlük mumda %0,1/gün yılda %28 demek (çok kaba), 6 aylık kovada
 * ise aynı sayı hiçbir şey (çok ince). Ölçüldü: 90 günde -%6,37 olan gerçek
 * seri "Yatay" görünüyordu. Toplam değişim her kova uzunluğunda aynı şeyi ifade
 * eder, o yüzden karar oradan verilir.
 */
export const FLAT_LIMIT = 0.01;

export const trendLine = (values: readonly number[]): Trend | null => {
  const y: number[] = [];
  const x: number[] = [];
  values.forEach((v, i) => {
    if (Number.isFinite(v) && v > 0) { y.push(Math.log(v)); x.push(i); }
  });
  if (y.length < 2) return null;

  const n = y.length;
  const xOrt = x.reduce((a, b) => a + b, 0) / n;
  const yOrt = y.reduce((a, b) => a + b, 0) / n;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) {
    const dx = x[i] - xOrt, dy = y[i] - yOrt;
    sxy += dx * dy; sxx += dx * dx; syy += dy * dy;
  }
  if (sxx === 0) return null;

  /* Sabit seri: log değerleri birebir aynı olsa da toplayıp bölmek `yOrt`'u bir
     ULP kaydırabiliyor; o zaman `syy` sıfır yerine ~1e-31 çıkıyor ve r² anlamsız
     bir sayıya dönüşüyor (ölçüldü: yatay seride r² = 0). Log uzayında 1e-10'luk
     bir yayılım milyarda bir yüzde demektir; bu eşiğin altını düz kabul ediyoruz. */
  if (syy <= n * 1e-20) {
    const sabit = Math.exp(yOrt);
    return { slopePct: 0, first: sabit, last: sabit, r2: 1,
             at: () => sabit, changePct: 0, direction: 'flat',
             sigma: 0, band: () => sabit, lastZ: 0 };
  }

  const egim = sxy / sxx;                       // log-fiyat / adım
  const kesim = yOrt - egim * xOrt;
  const at = (i: number) => Math.exp(kesim + egim * i);
  const r2 = syy === 0 ? 1 : Math.min(1, Math.max(0, (sxy * sxy) / (sxx * syy)));

  /* Kanal: artıkların standart sapması. Log uzayında hesaplandığı için bant
     fiyat ekseninde çarpımsal açılır — yükselen bir seride üst bant alt banttan
     daha geniş görünür ve bu doğrudur, çünkü %8'lik sapma yüksek fiyatta daha
     çok dolar eder. */
  let kareler = 0;
  for (let i = 0; i < n; i++) { const e = y[i] - (kesim + egim * x[i]); kareler += e * e; }
  const sigma = Math.sqrt(kareler / n);
  const band = (i: number, k: number) => at(i) * Math.exp(k * sigma);
  const sonArtik = y[n - 1] - (kesim + egim * x[n - 1]);
  const lastZ = sigma > 0 ? sonArtik / sigma : 0;

  const ilk = at(0);
  const son = at(values.length - 1);
  const toplam = ilk > 0 ? son / ilk - 1 : 0;
  const slopePct = Math.expm1(egim);            // dönem başına oransal değişim
  return {
    slopePct, first: ilk, last: son, r2, at,
    changePct: toplam,
    direction: toplam > FLAT_LIMIT ? 'up' : toplam < -FLAT_LIMIT ? 'down' : 'flat',
    sigma, band, lastZ,
  };
};
