import type { MarketCandle } from '../dashboard/useTechnical';

/*
 * Grafik geometrisi — **finansal hesap yok.** Mumun ne olduğu sunucuda
 * tanımlıdır (`daily.body_definition = prev_close_to_close`: kaynakta açılış
 * olmadığı için gövde önceki kapanış → kapanış); burada yalnız o tanımın
 * çizime nasıl döküleceği vardır: hangi uç üstte, fitil nereden nereye,
 * gövde kaç piksel.
 */

/** Mum genişliği: gün başına düşen piksel, boşluk payıyla ve okunur sınırlarla. */
export const candleWidth = (pixelsPerDay: number): number =>
  Math.max(1, Math.min(14, pixelsPerDay * 0.68));

export type CandleShape = {
  /** Grafik x ekseni indeksi; son gün 0, geçmiş negatif. */
  i: number;
  date: string;
  /** Gövdenin üst ve alt ucu (fiyat). Sunucunun tanımıyla `pc` ve `c`; hangisi üstteyse. */
  bodyTop: number;
  bodyBottom: number;
  /** Fitil uçları; gövdeyi de kapsayacak şekilde genişletilmiş (aşağıya bak). */
  wickHigh: number;
  wickLow: number;
  /** Kapanış ucu gövdenin üstündeyse yükseliş rengi. Sunucunun gövde tanımının çizimi, karar değil. */
  up: boolean;
  /** Ölçülmüş gün içi yüksek/düşük; ipucu kartı bunları yazar. */
  high: number;
  low: number;
};

/**
 * Sunucudan gelen günlük mumları (tarih, h, l, c, pc) çizim şekline çevirir.
 *
 * Fitil `max(h, c, pc)` – `min(l, c, pc)` alınır: kaynak nadiren kapanışı
 * gün aralığının dışında verebiliyor ve gövde fitilin dışına taşarsa şekil
 * çelişkili görünür. Bu, sunucunun gövde tanımının (önceki kapanış → kapanış)
 * **çizimi**dir; hiçbir sayı üretilmez, yalnız hangi ucun nerede duracağı seçilir.
 * `pc` yoksa (serinin ilk mumu) gövde kapanışta sıfır yükseklikte kalır.
 */
export const candleShapes = (candles: MarketCandle[], rangeDays: number): CandleShape[] => {
  if (candles.length === 0 || rangeDays <= 0) return [];
  const shown = candles.slice(-rangeDays);
  const last = shown.length - 1;
  return shown.map((bar, index) => {
    const other = bar.pc ?? bar.c;
    return {
      i: index - last,
      date: bar.date,
      bodyTop: Math.max(bar.c, other),
      bodyBottom: Math.min(bar.c, other),
      wickHigh: Math.max(bar.h, bar.c, other),
      wickLow: Math.min(bar.l, bar.c, other),
      up: bar.c >= other,
      high: bar.h,
      low: bar.l,
    };
  });
};
