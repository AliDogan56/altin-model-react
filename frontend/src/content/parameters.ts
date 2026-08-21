import type { ParameterGroup } from './types';

export const GROUPS: ParameterGroup[] = [
  ['Fiyat ve teknik', [['price', 'Ons fiyatı', 'USD'], ['gold_rsi14', 'RSI (14)', ''], ['gold_atr14_pct', 'ATR (14)', '%'], ['gold_return_20d', '20 günlük momentum', '%'], ['gold_volatility_20d', '20 günlük oynaklık', '%']]],
  ['Faiz ve dolar', [['DGS10', 'ABD 10Y faiz', '%'], ['DGS2', 'ABD 2Y faiz', '%'], ['DFII10', '10Y reel faiz', '%'], ['DTWEXBGS', 'Dolar endeksi', ''], ['FEDFUNDS', 'Fed fon faizi', '%']]],
  ['Risk ve emtia', [['VIXCLS', 'VIX', ''], ['DCOILWTICO', 'WTI petrol', 'USD']]],
  ['Makroekonomi', [['CPIAUCSL_yoy_pct', 'TÜFE yıllık', '%'], ['CPILFESL_yoy_pct', 'Çekirdek TÜFE', '%'], ['PCEPI_yoy_pct', 'PCE yıllık', '%'], ['UNRATE', 'İşsizlik', '%'], ['RSAFS_mom_pct', 'Perakende satış aylık', '%']]],
];

export const PARAMETER_IDS = GROUPS.flatMap(([, items]) => items).map(([id]) => id);

/** Katkı kartında gösterilen, ekonomik olarak en okunaklı sekiz girdi. */
export const IMPACT_NAMES: Record<string, string> = {
  DFII10: '10Y reel faiz', DTWEXBGS: 'Dolar endeksi', DGS10: '10Y tahvil faizi', VIXCLS: 'VIX (risk iştahı)',
  CPIAUCSL_yoy_pct: 'TÜFE (yıllık)', CPILFESL_yoy_pct: 'Çekirdek TÜFE', UNRATE: 'İşsizlik',
  gold_return_20d: '20 günlük momentum',
};
