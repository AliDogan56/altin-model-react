/**
 * Yükleme göstergesinin asgari görünme süresi — saf karar mantığı.
 *
 * Veri 80 ms'de geldiğinde spinner tek karede görünüp kayboluyor ve kullanıcı
 * bunu "bir şey titredi" olarak okuyor; dolum animasyonu hiç görünmüyor.
 * Burası "şu an gösterilmeli mi, değilse ne kadar sonra kaldırılmalı" sorusunu
 * React'ten bağımsız cevaplar; `app/useMinVisible.ts` yalnız ince bir sarmalayıcıdır.
 */

export type HoldState = { held: boolean; startedAt: number };

/** Sikkenin bir kez dolduğu an: `spinner-fill` 2,1 sn döngüsünün %55'i. */
export const MIN_SPINNER_MS = 1150;

export type HoldStep = {
  state: HoldState;
  /** null ise zamanlayıcı gerekmiyor; sayı ise bu kadar ms sonra tekrar bak. */
  timeoutIn: number | null;
};

/**
 * @param prev    önceki tutma durumu
 * @param active  ham yükleme koşulu (veri gerçekten bekleniyor mu)
 * @param now     şimdiki zaman damgası
 * @param minMs   asgari görünme süresi
 */
export const nextHold = (
  prev: HoldState, active: boolean, now: number, minMs: number = MIN_SPINNER_MS,
): HoldStep => {
  if (active) {
    // Değişiklik yoksa **aynı nesne** dönmeli. Yeni nesne dönmek, durumu
    // effect içinde güncelleyen çağıranda sonsuz render döngüsü yaratıyor
    // ("Maximum update depth exceeded"); grafik ilk yüklemede patlıyordu.
    // Zaten tutuluyorsa sayaç da sıfırlanmaz: art arda gelen güncellemeler
    // asgari süreyi sonsuza kadar uzatırdı.
    if (prev.held) return { state: prev, timeoutIn: null };
    return { state: { held: true, startedAt: now }, timeoutIn: null };
  }
  if (!prev.held) return { state: prev, timeoutIn: null };

  const remaining = minMs - (now - prev.startedAt);
  if (remaining <= 0) return { state: { held: false, startedAt: prev.startedAt }, timeoutIn: null };
  return { state: prev, timeoutIn: remaining };
};
