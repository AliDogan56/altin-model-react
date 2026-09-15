/**
 * "Yeni yorum" kararı (saf): son görülen yorumun üretim zamanı saklanır; sunucudaki yorumun
 * üretim zamanı ondan büyükse yeni. Cihaz saati değil yorumun kendi damgası saklanır, saat
 * kayması sonucu bozmaz. İlk ziyarette hiçbir şey saklı değildir; o zaman da rozet yanar (ürün
 * kararı, 2026-09-15: yeni okuyucu yorumun varlığını görsün). Okuyucu ilk yorumu okuyunca damga
 * düşer, o andan sonra yalnız daha yeni üretimler "yeni" olur.
 */
export const SEEN_AT_KEY = 'oaa-commentary-seen-at';
/** Pencere bu kadar açık kaldıysa, dinleme başladıysa ya da metnin yarısı geçildiyse okundu sayılır. */
export const SEEN_AFTER_MS = 5000;
export const SEEN_SCROLL_RATIO = 0.5;

const time = (iso: string | null | undefined): number => {
  if (!iso) return Number.NaN;
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : Number.NaN;
};

export const isUnread = (generatedAt: string | null | undefined, lastSeenAt: string | null | undefined): boolean => {
  const g = time(generatedAt);
  if (!Number.isFinite(g)) return false;
  const s = time(lastSeenAt);
  if (!Number.isFinite(s)) return true;           // ilk ziyaret ya da bozuk damga: henüz okunmamış sayılır
  return g > s;
};

export const ageMinutes = (generatedAt: string | null | undefined, now: number = Date.now()): number | null => {
  const g = time(generatedAt);
  return Number.isFinite(g) ? Math.max(0, Math.round((now - g) / 60000)) : null;
};

export const ageLabel = (minutes: number | null): string => {
  if (minutes == null) return '';
  if (minutes < 1) return 'şimdi';
  if (minutes < 60) return `${minutes} dk`;
  const h = Math.floor(minutes / 60);
  return h < 24 ? `${h} sa` : `${Math.floor(h / 24)} gün`;
};

export const shouldMarkSeen = (state: { openMs: number; scrolledRatio: number; listened: boolean }): boolean =>
  state.listened || state.openMs >= SEEN_AFTER_MS || state.scrolledRatio >= SEEN_SCROLL_RATIO;

export const readSeenAt = (): string | null => { try { return window.localStorage.getItem(SEEN_AT_KEY); } catch { return null; } };
export const writeSeenAt = (iso: string): void => { try { window.localStorage.setItem(SEEN_AT_KEY, iso); } catch { /* depolama yoksa oturumla sınırlı */ } };
