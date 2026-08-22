export type RawQuote = {
  alis: number; satis: number; dir: string;
  low: number; high: number; prev: number; time: string;
};

export type ReadQuote = {
  spread: number;
  /** Gün aralığı çubuğu gösterilebilir mi. */
  hasRange: boolean;
  /** Satış fiyatının gün aralığındaki konumu (%), aralık geçersizse null. */
  at: number | null;
  /** Önceki kapanışa göre değişim; kapanış doğrulanamazsa null. */
  change: number | null;
};

/** Gün aralığı fiyatın en fazla bu kadar altına inebilir; altındaki "düşük" bozuktur. */
const MIN_LOW_RATIO = 0.5;
/** Önceki kapanış, gün aralığından en fazla bu kadar bant uzakta olabilir. */
const PREV_TOLERANCE = 0.5;

/**
 * Harem kotasyonunu ekrana koymadan önce doğrular.
 *
 * `dusuk` alanı çeyrek/yarım/tam altında ₺5–₺20 gibi imkânsız değerlerle geliyor;
 * `kapanis` ise bayat kalabiliyor (gram için ons ve kur düz iken %6 artış iddia
 * ediyordu). Eski kontrol toleransı bozuk `dusuk`tan türettiği için kendini
 * savunamıyordu: önce aralık doğrulanır, yüzde ancak geçerli aralığa dayanırsa
 * gösterilir.
 */
export const readQuote = ({ alis, satis, low, high, prev }: RawQuote): ReadQuote => {
  const spread = satis - alis;
  const hasRange = low > 0 && high > low
    && low >= satis * MIN_LOW_RATIO
    && satis >= low && satis <= high;

  if (!hasRange) return { spread, hasRange: false, at: null, change: null };

  const band = high - low;
  const at = Math.min(100, Math.max(0, (satis - low) / band * 100));
  const trusted = prev > 0 && prev >= low - band * PREV_TOLERANCE && prev <= high + band * PREV_TOLERANCE;
  return { spread, hasRange: true, at, change: trusted ? satis / prev - 1 : null };
};
