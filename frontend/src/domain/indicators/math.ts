export const sma = (a: number[], n: number, i = a.length - 1): number | null =>
  i + 1 < n ? null : a.slice(i + 1 - n, i + 1).reduce((s, v) => s + v, 0) / n;

/** İlk n-1 değer null döner; öncesi ısınma penceresidir. */
export const emaSeries = (a: number[], n: number): (number | null)[] => {
  const k = 2 / (n + 1);
  const out: (number | null)[] = [];
  let prev = 0;
  a.forEach((v, i) => { prev = i === 0 ? v : v * k + prev * (1 - k); out.push(i + 1 < n ? null : prev); });
  return out;
};

/** Wilder yumuşatması: ilk n değerin toplamı, sonrası acc - acc/n + yeni. */
export const wilder = (a: number[], n: number): (number | null)[] => {
  const out: (number | null)[] = new Array(a.length).fill(null);
  if (a.length < n) return out;
  let acc = a.slice(0, n).reduce((s, v) => s + v, 0);
  out[n - 1] = acc;
  for (let i = n; i < a.length; i++) { acc = acc - acc / n + a[i]; out[i] = acc; }
  return out;
};
