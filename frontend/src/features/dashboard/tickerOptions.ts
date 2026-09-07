/**
 * Başlık kartındaki seçilebilir göstergeler. USD/TRY sabittir; kalan üç yuva
 * canlı piyasa kotasyonlarından (ziynet ürünleri, Harem) ya da makro girdilerden
 * (`/v1/features/latest`) seçilir. Saf modül: seçim doğrulama, yuva değiştirme
 * (takas) ve değer biçimleme burada, React bilmez.
 */
import { ZIYNET_SPECS } from '../../domain/ziynet';
import type { FeatureMap } from '../../domain/model/types';
import { pct, tryMoney } from '../../lib/format';
import { ZIYNET } from '../../services/realtime/harem';
import type { Quote } from '../../services/realtime/types';

export type TickerGroup = 'market' | 'macro';
type Kind = 'try' | 'pct' | 'points' | 'level' | 'pct_units';
export type TickerOption = { id: string; group: TickerGroup; label: string; note: string; kind: Kind };

const milyem = (code: string): string => {
  const spec = ZIYNET_SPECS[code];
  return spec ? `${Math.round(spec.fineness * 1000)} · satış fiyatı` : 'satış fiyatı';
};

export const TICKER_OPTIONS: readonly TickerOption[] = [
  ...ZIYNET.map(([code, label]): TickerOption => ({ id: code, group: 'market', label, note: milyem(code), kind: 'try' })),
  { id: 'dollar_return_5d', group: 'macro', label: 'Dolar endeksi', note: 'Geniş dolar · 5 gün', kind: 'pct' },
  { id: 'real_yield_change_5d', group: 'macro', label: 'Reel faiz', note: '10 yıllık · 5 gün', kind: 'points' },
  { id: 'vix_level', group: 'macro', label: 'VIX', note: 'Oynaklık endeksi · seviye', kind: 'level' },
  { id: 'oil_return_5d', group: 'macro', label: 'Petrol', note: 'WTI · 5 gün', kind: 'pct' },
  { id: 'yield_curve_10y_2y', group: 'macro', label: 'Getiri eğrisi', note: 'ABD 10Y − 2Y', kind: 'points' },
  { id: 'core_cpi_yoy', group: 'macro', label: 'ABD enflasyonu', note: 'Çekirdek TÜFE · yıllık', kind: 'pct_units' },
];

export const GROUP_LABEL: Record<TickerGroup, string> = { market: 'Canlı piyasa', macro: 'Makro' };

/** Kartın eski sabit hâli: gram altın, dolar endeksi, reel faiz. */
export const DEFAULT_SLOTS: readonly string[] = ['ALTIN', 'dollar_return_5d', 'real_yield_change_5d'];
export const SLOT_COUNT = DEFAULT_SLOTS.length;
export const SLOTS_STORAGE_KEY = 'oaa-ticker-slots';

export const optionOf = (id: string): TickerOption | undefined => TICKER_OPTIONS.find(o => o.id === id);

/**
 * Saklanan seçimi doğrular: tam `SLOT_COUNT` adet, tanınan ve tekrar etmeyen
 * kimlik; bozuk ya da eksik yuvalar varsayılanlardan (kullanılmayan ilk) doldurulur.
 */
export const normalizeSlots = (raw: unknown): string[] => {
  const picked: string[] = [];
  if (Array.isArray(raw)) {
    for (const item of raw) {
      if (typeof item === 'string' && optionOf(item) && !picked.includes(item)) picked.push(item);
      if (picked.length === SLOT_COUNT) break;
    }
  }
  for (const id of DEFAULT_SLOTS) {
    if (picked.length === SLOT_COUNT) break;
    if (!picked.includes(id)) picked.push(id);
  }
  return picked;
};

/**
 * Bir yuvaya gösterge atar. Gösterge başka bir yuvada seçiliyse iki yuva yer
 * değiştirir: aynı gösterge iki kez görünmez, kullanıcı da "önce boşalt" zorunda kalmaz.
 */
export const applySlot = (slots: readonly string[], index: number, id: string): string[] => {
  if (!optionOf(id) || index < 0 || index >= slots.length || slots[index] === id) return [...slots];
  const next = [...slots];
  const other = next.indexOf(id);
  if (other >= 0) next[other] = next[index];
  next[index] = id;
  return next;
};

const signed = (value: number, digits: number): string => `${value > 0 ? '+' : ''}${value.toFixed(digits)}`;

/** Yuvanın gösterdiği metin; veri yoksa `null` (arayüz "—" basar). */
export const tickerValue = (id: string, data: { ziynet: Record<string, Quote>; live: FeatureMap }): string | null => {
  const option = optionOf(id);
  if (!option) return null;
  if (option.kind === 'try') {
    const satis = data.ziynet[id]?.satis;
    return typeof satis === 'number' && Number.isFinite(satis) && satis > 0 ? tryMoney(satis) : null;
  }
  const value = data.live[id];
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  switch (option.kind) {
    case 'pct': return pct(value);
    case 'points': return `${signed(value, 2)} puan`;
    case 'level': return value.toFixed(1);
    case 'pct_units': return pct(value / 100);
  }
};

export const readStoredSlots = (): string[] => {
  try {
    return normalizeSlots(JSON.parse(window.localStorage.getItem(SLOTS_STORAGE_KEY) ?? 'null'));
  } catch {
    // Gizli sekme, depolama kapalı ya da bozuk JSON: varsayılan yeter.
    return normalizeSlots(null);
  }
};

export const storeSlots = (slots: readonly string[]): void => {
  try { window.localStorage.setItem(SLOTS_STORAGE_KEY, JSON.stringify(slots)); } catch { /* depolama yoksa seçim oturumla sınırlı */ }
};
