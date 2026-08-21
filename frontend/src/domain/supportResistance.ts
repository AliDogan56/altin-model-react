export type Level = { price: number; touches: number };

/** k=5 ve %1,5 tolerans gerçek veriyle denendiğinde 10 pivot bulup sıfır küme üretti;
 *  aşağıdaki değerler ölçülerek seçildi. */
const PIVOT_WINDOW = 3;
const TOLERANCE_RATIO = 0.055;   // görünen aralığın %5,5'i ≈ fiyatın %1,3'ü
const MIN_TOUCHES = 2;
const MAX_LEVELS = 4;

/**
 * Görünen geçmişteki dönüş noktaları bulunur, birbirine yakın olanlar tek seviyede
 * kümelenir ve en çok dokunulan dördü döner. Fiyatın üstünde kalanlar direnç,
 * altında kalanlar destek olarak okunur.
 */
export const findLevels = (values: number[]): Level[] => {
  const k = PIVOT_WINDOW;
  if (values.length < 2 * k + 4) return [];
  const span = Math.max(...values) - Math.min(...values);
  const tolerance = (span || 1) * TOLERANCE_RATIO;

  const pivots: number[] = [];
  for (let i = k; i < values.length - k; i++) {
    const window = values.slice(i - k, i + k + 1);
    if (values[i] === Math.max(...window) || values[i] === Math.min(...window)) pivots.push(values[i]);
  }

  const clusters: { price: number; hits: number[] }[] = [];
  pivots.sort((a, b) => a - b).forEach(value => {
    const last = clusters[clusters.length - 1];
    if (last && value - last.price <= tolerance) {
      last.hits.push(value);
      last.price = last.hits.reduce((s, v) => s + v, 0) / last.hits.length;
    } else clusters.push({ price: value, hits: [value] });
  });

  return clusters
    .filter(c => c.hits.length >= MIN_TOUCHES)
    .sort((a, b) => b.hits.length - a.hits.length)
    .slice(0, MAX_LEVELS)
    .map(c => ({ price: c.price, touches: c.hits.length }));
};
