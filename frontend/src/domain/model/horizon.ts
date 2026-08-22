export type ResolvedHorizon = { index: number; horizon: number; exact: boolean };

/**
 * Seçili ufkun modeldeki karşılığı.
 *
 * Çağrı yerlerinde `Math.max(0, horizons.indexOf(x))` kullanılıyordu: ufuk
 * listede yoksa sessizce ilk ufka düşüyor, kart ise istenen vadeyi yazmaya
 * devam ediyordu. Artık hangi ufkun kullanıldığı ve tam eşleşme olup olmadığı
 * çağırana bildirilir.
 */
export const resolveHorizon = (horizons: number[], requested: number): ResolvedHorizon => {
  if (!horizons.length) return { index: 0, horizon: requested, exact: false };
  const exact = horizons.indexOf(requested);
  if (exact >= 0) return { index: exact, horizon: requested, exact: true };
  let index = 0;
  horizons.forEach((horizon, i) => {
    if (Math.abs(horizon - requested) < Math.abs(horizons[index] - requested)) index = i;
  });
  return { index, horizon: horizons[index], exact: false };
};
