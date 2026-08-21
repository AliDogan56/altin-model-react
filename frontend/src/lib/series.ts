export type SeriesPoint = { date: string; value: number };

/** FRED CSV'si: ilk satır başlık, eksik değerler "." olarak gelir ve elenir. */
export const parseCsv = (text: string): SeriesPoint[] =>
  text.trim().split(/\r?\n/).slice(1)
    .map(line => { const [date, value] = line.split(','); return { date, value: +value }; })
    .filter(x => Number.isFinite(x.value));

/** Takvim günü bazlı geriye dönük okuma: seri o günde yoksa önceki en yakın değer. */
export const asOf = (rows: SeriesPoint[], day: string): number | null => {
  for (let i = rows.length - 1; i >= 0; i--) if (rows[i].date <= day) return rows[i].value;
  return null;
};

export const shiftDays = (day: string, n: number): string => {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - n);
  return d.toISOString().slice(0, 10);
};
