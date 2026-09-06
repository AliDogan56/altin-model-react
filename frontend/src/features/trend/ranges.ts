import { RANGE, type RangeId } from '../../content/trend';

/**
 * Trend kartının aralık düğmeleri. Aralığın kova birimi, nokta sayısı ve mum/çizgi
 * seçimi artık **sunucudan** gelir (`trend.ranges[id]`: `timeframe`, `bars`,
 * `candles`); burada yalnız kimlik ve etiket kalır. Kimlikler sunucunun
 * `ranges` anahtarlarıyla birebir — bir kimlik yanıtta yoksa kart o aralık için
 * durum metni gösterir, kendi kovasını kurmaz.
 */
export type { RangeId };

export const RANGE_IDS: readonly RangeId[] = ['gunluk', 'haftalik', 'aylik', 'ceyreklik', 'yarim'];

export const RANGES = RANGE_IDS.map(id => ({ id, ...RANGE[id] }));

export const DEFAULT_RANGE: RangeId = 'gunluk';
