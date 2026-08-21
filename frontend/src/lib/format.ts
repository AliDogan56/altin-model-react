const tr = (options: Intl.NumberFormatOptions) => new Intl.NumberFormat('tr-TR', options);

export const money = (v: number) => tr({ style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(v);
export const money2 = (v: number) => tr({ style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);
export const tryMoney = (v: number) => tr({ style: 'currency', currency: 'TRY', maximumFractionDigits: 0 }).format(v);
export const tryAmount = (v: unknown) => tr({ maximumFractionDigits: 0 }).format(Math.max(0, Number(v) || 0));
export const tryRate = (v: unknown) => tr({ minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(Number(v) || 0);

export const pct = (v: number) => tr({ style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(v);

/** Hata metrikleri binde mertebesinde; tek ondalık iki farklı sayıyı aynı gösteriyordu. */
export const pct2 = (v: number) => tr({ style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);

export const signedPct2 = (v: number) =>
  `${v >= 0 ? '+' : ''}${tr({ minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v * 100)}%`;

export const points = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)} puan`;

const fullDate = new Intl.DateTimeFormat('tr-TR', { day: '2-digit', month: 'long', year: 'numeric' });

/** Eksen etiketi. Intl'in tr-TR kısa biçimi ortama göre '14/08' verebiliyor;
 *  eksende nokta ayracı bekleniyor, bu yüzden ISO parçalarından kuruluyor.
 *  Ayrıca `new Date(iso)` UTC ayrıştırıp günü kaydırma riskini de ortadan kaldırır. */
export const shortDate = (iso: string, withYear = false) => {
  const [year, month, day] = iso.split('-');
  return withYear ? `${day}.${month}.${year.slice(2)}` : `${day}.${month}`;
};

export const longDate = (iso: string) => fullDate.format(new Date(`${iso}T00:00:00`));
