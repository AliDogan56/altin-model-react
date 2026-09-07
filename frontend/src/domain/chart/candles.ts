import type { Candle } from '../indicators';

/**
 * Grafikte çizilecek günlük mumlar.
 *
 * **Veri kısıtı:** Fiyat kaynağı (xaus.com) her gün için yalnız tarih, kapanış,
 * gün içi yüksek ve düşük veriyor; **açılış yok**. Bu yüzden gövde, klasik
 * mumdaki "açılış → kapanış" yerine **önceki kapanış → bugünkü kapanış**
 * aralığını gösterir; yani günün net hareketini. Fitil ise kaynaktan gelen
 * gerçek gün içi yüksek/düşük aralığıdır.
 *
 * Sonuçta grafikteki her sayı ölçülmüş veridir; farklı olan tek şey gövdenin
 * tanımıdır ve arayüzde bu açıkça yazılır. Spot altın kesintisiz işlem gördüğü
 * için önceki kapanış, açılışa pratikte çok yakındır; hafta sonu boşluklarında
 * ise gövde o boşluğu da kapsar ve bu doğru bir bilgidir.
 */
export type ChartCandle = {
  /** Grafik x ekseni indeksi; son gün 0, geçmiş negatif. */
  i: number;
  date: string;
  /** Önceki kapanış — kaynakta açılış olmadığı için gövdenin alt/üst ucu. */
  open: number;
  high: number;
  low: number;
  close: number;
  /** Kapanış önceki kapanışın üzerindeyse yükseliş mumu. */
  up: boolean;
};

/**
 * @param candles  tarih sıralı günlük seri (en yeni sonda)
 * @param rangeDays kaç gün gösterilecek
 */
export const buildCandles = (candles: Candle[], rangeDays: number): ChartCandle[] => {
  if (candles.length === 0 || rangeDays <= 0) return [];

  // Bir gün fazlasını alıyoruz: ilk mumun gövdesi için önceki kapanış gerekli.
  const from = Math.max(0, candles.length - rangeDays - 1);
  const slice = candles.slice(from);
  const shown = slice.length > rangeDays ? slice.slice(1) : slice;
  const last = shown.length - 1;

  return shown.map((bar, index) => {
    const previous = slice[slice.length - shown.length + index - 1];
    // Serinin en başında önceki gün yok; gövde sıfır yükseklikte kalır.
    const open = previous ? previous.c : bar.c;
    return {
      i: index - last,
      date: bar.date,
      open,
      // Kaynak nadiren kapanışı gün aralığının dışında verebiliyor; gövde ile
      // fitil çelişmesin diye aralığı ikisini de kapsayacak şekilde genişletiriz.
      high: Math.max(bar.h, bar.c, open),
      low: Math.min(bar.l, bar.c, open),
      close: bar.c,
      up: bar.c >= open,
    };
  });
};

/** Mum genişliği: gün başına düşen piksel, boşluk payıyla ve okunur sınırlarla. */
export const candleWidth = (pixelsPerDay: number): number =>
  Math.max(1, Math.min(14, pixelsPerDay * 0.68));
