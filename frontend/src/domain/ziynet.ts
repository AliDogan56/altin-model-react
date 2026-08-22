import { readQuote, type RawQuote, type ReadQuote } from './quotes';

/** Bir troy ons = 31,1035 gram. */
export const GRAMS_PER_OUNCE = 31.1035;

export type ZiynetSpec = { label: string; grams: number; fineness: number };

/** Ürünlerin resmî gram ve milyem değerleri; ham altın değeri bunlardan türer. */
export const ZIYNET_SPECS: Record<string, ZiynetSpec> = {
  ALTIN: { label: 'Gram altın', grams: 1, fineness: 0.995 },
  AYAR22: { label: '22 ayar gram', grams: 1, fineness: 0.916 },
  CEYREK_YENI: { label: 'Çeyrek (yeni)', grams: 1.75, fineness: 0.916 },
  YARIM_YENI: { label: 'Yarım (yeni)', grams: 3.5, fineness: 0.916 },
  TEK_YENI: { label: 'Tam (yeni)', grams: 7, fineness: 0.916 },
  ATA_YENI: { label: 'Yeni Ata', grams: 7.216, fineness: 0.916 },
};

export type ZiynetRow = ReadQuote & {
  code: string; label: string;
  /** Ürünün içindeki saf altın (gram). */
  pureGrams: number;
  satis: number; alis: number; dir: string;
  /** Alış-satış makasının satışa oranı. */
  spreadPct: number;
  /** Canlı ons ve kurdan türeyen ham altın değeri; kur yoksa null. */
  rawValue: number | null;
  /** Piyasa fiyatının ham değerin ne kadar üstünde olduğu (işçilik + marj). */
  premium: number | null;
};

/** 1 gram saf altının TL karşılığı. */
export const pureGramPrice = (onsUsd: number, usdTry: number): number | null =>
  onsUsd > 0 && usdTry > 0 ? onsUsd * usdTry / GRAMS_PER_OUNCE : null;

/**
 * Kart, kaynağın `dusuk`/`kapanis` alanları bozuk olduğunda neredeyse boş kalıyordu.
 * Oysa her üründe **her zaman** güvenilir olan üç şey var: alış, satış ve ürünün
 * saf altın içeriği. Bunlardan ham altın değeri ve işçilik payı hesaplanabilir —
 * kartın asıl anlattığı şey de bu.
 */
export const buildZiynetRows = (
  quotes: Record<string, RawQuote>, onsUsd: number, usdTry: number, order: string[] = Object.keys(ZIYNET_SPECS),
): ZiynetRow[] => {
  const gramPrice = pureGramPrice(onsUsd, usdTry);
  return order.filter(code => quotes[code] && ZIYNET_SPECS[code]).map(code => {
    const quote = quotes[code];
    const spec = ZIYNET_SPECS[code];
    const pureGrams = spec.grams * spec.fineness;
    const rawValue = gramPrice == null ? null : gramPrice * pureGrams;
    return {
      ...readQuote(quote),
      code, label: spec.label, pureGrams,
      satis: quote.satis, alis: quote.alis, dir: quote.dir,
      spreadPct: quote.satis > 0 ? (quote.satis - quote.alis) / quote.satis : 0,
      rawValue,
      premium: rawValue && rawValue > 0 ? quote.satis / rawValue - 1 : null,
    };
  });
};
