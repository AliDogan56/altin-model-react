/**
 * Yorum metni yazıldığı andaki fiyata göre kurulur; okuyucu pencereyi çok sonra
 * açabilir. Kart o anki canlı kotasyonu gösterir ve metnin hangi fiyatla yazıldığını,
 * o zamandan beri fiyatın ne kadar oynadığını ayrıca söyler. Servisin yeniden
 * yazma eşiği %0,5 (`TRIGGER_MOVE_PCT`); fark onu aşınca "masa yeniden yazacak" notu çıkar.
 */
export const REGENERATE_MOVE_PCT = 0.5;

export type Drift = { pct: number; usd: number; beyondTrigger: boolean };

export const driftSinceGeneration = (livePrice: number | null | undefined, generationPrice: number | null | undefined): Drift | null => {
  if (!livePrice || !generationPrice || livePrice <= 0 || generationPrice <= 0) return null;
  const usd = livePrice - generationPrice;
  const pct = (livePrice / generationPrice - 1) * 100;
  return { pct, usd, beyondTrigger: Math.abs(pct) >= REGENERATE_MOVE_PCT };
};
