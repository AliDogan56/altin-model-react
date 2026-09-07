import type { Bucket } from '../../domain/chart/aggregate';

/**
 * Trend kartının zaman aralıkları. Her aralık günlük seriyi farklı bir kovaya
 * toplar; `bars` o kovadan kaç nokta gösterileceğidir.
 *
 * Kaynak beş yıllık günlük seri olduğu için üst aralıklarda nokta sayısı doğal
 * olarak azdır (6 aylıkta ~10). Bu bir eksiklik değil: trend çizgisi az sayıda
 * uzun dönemli noktadan da hesaplanabilir, yeter ki nokta sayısı bildirilsin.
 */
export type RangeId = 'gunluk' | 'haftalik' | 'aylik' | 'ceyreklik' | 'yarim';

export type RangeSpec = {
  id: RangeId; label: string; bucket: Bucket;
  /** Gösterilecek en fazla nokta. */
  bars: number;
  /** Günlük görünüm mum, diğerleri çizgi. */
  candles: boolean;
  /** Trend eğiminin birimi ("dönem başına …"). */
  unit: string;
};

export const RANGES: RangeSpec[] = [
  { id: 'gunluk',    label: 'Günlük',   bucket: 'gun',     bars: 90,  candles: true,  unit: 'gün' },
  { id: 'haftalik',  label: 'Haftalık', bucket: 'hafta',   bars: 104, candles: false, unit: 'hafta' },
  { id: 'aylik',     label: 'Aylık',    bucket: 'ay',      bars: 60,  candles: false, unit: 'ay' },
  { id: 'ceyreklik', label: '3 Aylık',  bucket: 'ceyrek',  bars: 24,  candles: false, unit: 'çeyrek' },
  { id: 'yarim',     label: '6 Aylık',  bucket: 'yariyil', bars: 12,  candles: false, unit: 'yarıyıl' },
];

export const DEFAULT_RANGE: RangeId = 'gunluk';
export const rangeById = (id: RangeId): RangeSpec =>
  RANGES.find(r => r.id === id) ?? RANGES[0];
