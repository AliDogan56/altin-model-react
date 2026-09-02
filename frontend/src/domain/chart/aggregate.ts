import type { Candle } from '../indicators';

/**
 * Günlük mumları daha uzun dönemlere toplar.
 *
 * Kaynak yalnız günlük OHLC veriyor (`Candle = { date, h, l, c }`, açılış yok).
 * Haftalık ve üstü görünümler için yeni bir uç gerekmez: aynı seriden türetilir.
 * Her kova için yüksek = kovanın en yükseği, düşük = en düşüğü, kapanış =
 * kovadaki **son** günün kapanışı. Tarih olarak kovanın ilk günü kullanılır.
 */
export type Bucket = 'gun' | 'hafta' | 'ay' | 'ceyrek' | 'yariyil';

/** Kova anahtarı: aynı anahtarı paylaşan günler tek muma toplanır. */
export const bucketKey = (iso: string, bucket: Bucket): string => {
  const [y, m, d] = iso.split('-').map(Number);
  if (bucket === 'gun') return iso;
  if (bucket === 'hafta') {
    // ISO hafta: pazartesiye çekilir, böylece hafta sınırı takvimle uyumlu olur.
    const t = Date.UTC(y, m - 1, d);
    const gun = (new Date(t).getUTCDay() + 6) % 7;          // pazartesi = 0
    return new Date(t - gun * 86400000).toISOString().slice(0, 10);
  }
  if (bucket === 'ay') return `${y}-${String(m).padStart(2, '0')}`;
  if (bucket === 'ceyrek') return `${y}-C${Math.floor((m - 1) / 3) + 1}`;
  return `${y}-Y${m <= 6 ? 1 : 2}`;
};

export const aggregate = (candles: readonly Candle[], bucket: Bucket): Candle[] => {
  if (bucket === 'gun') return candles.slice();
  const out: Candle[] = [];
  let anahtar = '';
  for (const c of candles) {
    if (!Number.isFinite(c.c) || !Number.isFinite(c.h) || !Number.isFinite(c.l)) continue;
    const k = bucketKey(c.date, bucket);
    if (k !== anahtar) {
      anahtar = k;
      out.push({ date: c.date, h: c.h, l: c.l, c: c.c });
      continue;
    }
    const son = out[out.length - 1];
    son.h = Math.max(son.h, c.h);
    son.l = Math.min(son.l, c.l);
    son.c = c.c;                                   // kovanın son kapanışı
  }
  return out;
};
