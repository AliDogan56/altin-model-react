/** AI yorumu düğmesi ve penceresinin metinleri; üçüncü taraf adları burada çevrilir. */
export const COMMENTARY_TEXT = {
  button: 'AI yorumu',
  kicker: 'Yapay zekâ masasının okuması',
  title: 'Ons AI yorumu',
  close: 'Kapat',
  pending: 'Masa ilk yorumu hazırlıyor; fiyat verisi toplanıp beş uzman rolü sırayla yazınca burada görünecek.',
  error: 'Yorum servisi şu an yanıt vermiyor; biraz sonra tekrar deneyin.',
  loading: 'Yorum yükleniyor',
  generatedAt: 'Son yorum',
  live: 'Canlı fiyat',
  writtenAt: 'Yorum yazılırken',
  sinceThen: 'o zamandan beri',
  driftNote: 'Fiyat yorum yazıldığından beri yarım yüzdeden fazla oynadı; masa bir sonraki kontrolde (en geç bir saat içinde) yeniden yazar. Metindeki sayılar yazıldığı anın sayılarıdır.',
  fix: 'Resmi fiks',
  vsFix: 'fikse göre',
  newBadge: 'Yeni yorum var',
  legal: 'İstatistiksel yorum · yatırım tavsiyesi değildir',
  listen: 'Dinle', pause: 'Duraklat', resume: 'Devam et', stop: 'Durdur',
  speakingStatus: 'Yorum cihazın sesiyle okunuyor; okunan bölüm vurgulanır.',
  pausedStatus: 'Okuma duraklatıldı.',
} as const;

/** Servisin `live.source` alanı kaynak kodu taşır; arayüzde ad değil çerçeve yazılır. */
export const liveSourceLabel = (source: string): string => {
  const s = source.toUpperCase();
  if (s.includes('PAXG')) return 'spot izleyen seri';
  if (s.includes('GC=F') || s.includes('VADELI') || s.includes('VADELİ')) return 'vadeli altın';
  return 'canlı seri';
};

/** Üretim yaşı: 4 saat (servisin `MAX_AGE_MINUTES`) sonra "eski" sayılır. */
export const COMMENTARY_STALE_MS = 4 * 60 * 60 * 1000;
