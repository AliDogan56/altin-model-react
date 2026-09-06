/** Teknik paketin referans fiyatı (gün içi son mum ya da günlük kapanış); Harem kotasyonu değil.
 *  Sunucu değer vermediyse `null` kalır — başka çerçeveden (son mum) doldurulmaz. */
export type SpotState = { price: number | null; time: Date | null; live: boolean };
export type RateState = { alis: number | null; satis: number | null; time: Date | null; live: boolean };
export type Quote = { alis: number; satis: number; dir: string; low: number; high: number; prev: number; time: string };
