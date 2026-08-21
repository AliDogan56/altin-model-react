export type PriceDomain = { min: number; max: number; bandClipped: boolean };

/** Çekirdek seriler (gerçekleşen + tahmin çizgisi) yüksekliğin en az bu kadarını kaplar. */
export const MIN_CORE_SHARE = 0.5;
const PAD_RATIO = 0.08;

const finite = (values: number[]) => values.filter(Number.isFinite);

/**
 * Dikey ölçek. Belirsizlik bandı ufuk uzadıkça çekirdek seriden kat kat geniş
 * oluyor; hepsi aynı torbaya atıldığında gerçekleşen fiyat çizgisi yüksekliğin
 * %37'sine düşüyordu (90 gün, mobil). Band yalnız çekirdeğin payı
 * `minCoreShare`'in altına inmeyecek kadar dahil edilir; taşan uç kırpılır.
 * Kırpılan değerler ipucu kutusunda ve günlük tabloda tam olarak görünmeye devam eder.
 */
export const computeDomain = (
  core: number[], band: number[] = [], minCoreShare = MIN_CORE_SHARE, padRatio = PAD_RATIO,
): PriceDomain => {
  const c = finite(core);
  if (!c.length) return { min: 0, max: 1, bandClipped: false };

  let lo = Math.min(...c), hi = Math.max(...c);
  const coreSpan = hi - lo || Math.max(Math.abs(hi) * 0.01, 1);
  let bandClipped = false;

  const b = finite(band);
  if (b.length) {
    const wantLo = Math.min(lo, ...b), wantHi = Math.max(hi, ...b);
    // pad sonradan ekleneceği için bütçe pay oranından geri hesaplanır
    const maxSpan = coreSpan / minCoreShare / (1 + 2 * padRatio);
    if (wantHi - wantLo <= maxSpan) {
      lo = wantLo; hi = wantHi;
    } else {
      const budget = Math.max(0, maxSpan - (hi - lo));
      const needLo = lo - wantLo, needHi = wantHi - hi, total = needLo + needHi;
      if (total > 0) { lo -= budget * (needLo / total); hi += budget * (needHi / total); }
      bandClipped = true;
    }
  }

  if (hi === lo) { lo -= coreSpan / 2; hi += coreSpan / 2; }   // tek değerli seri
  const pad = (hi - lo) * padRatio;
  return { min: lo - pad, max: hi + pad, bandClipped };
};

/** Zaman ekseni için eşit aralıklı gün indeksleri; tekrarlar elenir. */
export const pickTimeTicks = (start: number, end: number, count: number): number[] => {
  if (!(end > start) || count < 2) return [];
  const step = (end - start) / (count - 1);
  const out: number[] = [];
  for (let k = 0; k < count; k++) {
    const i = Math.round(start + step * k);
    if (!out.includes(i)) out.push(i);
  }
  return out;
};

/** Etiketler çakışmasın: `keep` indeksine çok yakın olanlar atılır. */
export const dropNear = (ticks: number[], keep: number, minGap: number): number[] =>
  ticks.filter(i => Math.abs(i - keep) >= minGap);
