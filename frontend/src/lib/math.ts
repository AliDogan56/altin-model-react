export const avg = (a: number[]): number => a.reduce((s, v) => s + v, 0) / a.length;

export const std = (a: number[]): number => {
  const m = avg(a);
  return Math.sqrt(avg(a.map(v => (v - m) ** 2)));
};

export const clamp = (v: number, lo: number, hi: number): number => Math.max(lo, Math.min(hi, v));
