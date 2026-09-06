import type { Labeled } from './technical';

/**
 * Trend bloğunun sözlüğü; sabitler
 * `backend/market-service/app/services/technical/trend.py` ile birebir.
 * Kanal **betimleyicidir, sinyal değil** (ölçüldü: kanal dışına çıkmak dönüş
 * öngörmüyor); bu yüzden kanal konumu yönle renklendirilmez, yalnız ±2σ
 * uçları dikkat tonu alır.
 */

export type TrendDirection = 'UP' | 'DOWN' | 'FLAT';

export const DIRECTION: Record<TrendDirection, Labeled> = {
  UP: { label: 'Yükseliş', tone: 'up' },
  DOWN: { label: 'Düşüş', tone: 'down' },
  FLAT: { label: 'Yatay', tone: 'flat' },
};

export type ChannelState = 'BELOW_2SIGMA' | 'BELOW_1SIGMA' | 'NEAR_TREND' | 'ABOVE_1SIGMA' | 'ABOVE_2SIGMA';

/** `note` cümle içi kullanım için ("fiyat şu an …"). */
export const CHANNEL_STATE: Record<ChannelState, Labeled & { note: string }> = {
  BELOW_2SIGMA: { label: 'Kanalın 2σ altında', tone: 'warn', note: 'kanalın belirgin altında' },
  BELOW_1SIGMA: { label: 'Trendin 1σ altında', tone: 'flat', note: 'trendin altında' },
  NEAR_TREND: { label: 'Trend çizgisine yakın', tone: 'flat', note: 'trend çizgisine yakın' },
  ABOVE_1SIGMA: { label: 'Trendin 1σ üstünde', tone: 'flat', note: 'trendin üstünde' },
  ABOVE_2SIGMA: { label: 'Kanalın 2σ üstünde', tone: 'warn', note: 'kanalın belirgin üstünde' },
};

export type FitState = 'GOOD' | 'MODERATE' | 'WEAK';

/** r² tek başına okura bir şey söylemiyor; `note` sade dille karşılığı. */
export const FIT_STATE: Record<FitState, { label: string; note: string }> = {
  GOOD: { label: 'Uyum iyi', note: 'seyir trendi yakından izliyor' },
  MODERATE: { label: 'Uyum orta', note: 'seyir trend etrafında dalgalı' },
  WEAK: { label: 'Uyum zayıf', note: 'dağınık seyir, genel yön zayıf' },
};

export type RangeId = 'gunluk' | 'haftalik' | 'aylik' | 'ceyreklik' | 'yarim';

/** Aralık düğmeleri; `short` dar ekran etiketi. */
export const RANGE: Record<RangeId, { label: string; short: string }> = {
  gunluk: { label: 'Günlük', short: '1G' },
  haftalik: { label: 'Haftalık', short: '1H' },
  aylik: { label: 'Aylık', short: '1A' },
  ceyreklik: { label: '3 Aylık', short: '3A' },
  yarim: { label: '6 Aylık', short: '6A' },
};

export type Timeframe = 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'QUARTERLY' | 'SEMIANNUAL';

/** Kova birimi; eğim "dönem başına" okunurken kullanılır ("hafta başına %0,4"). */
export const TIMEFRAME: Record<Timeframe, string> = {
  DAILY: 'gün',
  WEEKLY: 'hafta',
  MONTHLY: 'ay',
  QUARTERLY: 'çeyrek',
  SEMIANNUAL: 'yarıyıl',
};
