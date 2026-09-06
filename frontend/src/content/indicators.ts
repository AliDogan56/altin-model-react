import { money2 } from '../lib/format';
import type { Labeled } from './technical';

/**
 * Teknik gösterge tablosunun sözlüğü. Anahtarlar ve durumlar
 * `backend/market-service/app/services/technical/indicators.py`
 * (`latest_indicators`, `IndicatorState`) ile birebir.
 */

export type IndicatorKey = 'rsi' | 'stochastic' | 'williams' | 'cci' | 'macd' | 'adx' | 'atr' | 'roc';

/** Ad + varsayılan periyot (`IndicatorParams`). */
export const INDICATOR_NAME: Record<IndicatorKey, string> = {
  rsi: 'RSI (14)',
  stochastic: 'Stochastic %K (14)',
  williams: 'Williams %R (14)',
  cci: 'CCI (20)',
  macd: 'MACD (12, 26, 9)',
  adx: 'ADX (14)',
  atr: 'ATR (14)',
  roc: 'ROC (12)',
};

export type IndicatorState =
  | 'OVERBOUGHT'
  | 'OVERSOLD'
  | 'NEUTRAL'
  | 'ABOVE_SIGNAL'
  | 'BELOW_SIGNAL'
  | 'TRENDING'
  | 'WEAK_TREND'
  | 'HIGH_VOLATILITY'
  | 'LOW_VOLATILITY'
  | 'NORMAL_VOLATILITY'
  | 'POSITIVE'
  | 'NEGATIVE'
  | 'ABOVE'
  | 'BELOW';

/**
 * `warn` = dikkat çeken ama yönsüz durum (uç bölge, güçlü trend, yüksek
 * oynaklık). ADX yönsüzdür; `TRENDING` yeşil olsaydı güçlü bir düşüş trendi
 * de "iyi" okunurdu, o yüzden `up` değil `warn`.
 */
export const INDICATOR_STATE: Record<IndicatorState, Labeled> = {
  OVERBOUGHT: { label: 'Aşırı alım', tone: 'warn' },
  OVERSOLD: { label: 'Aşırı satım', tone: 'warn' },
  NEUTRAL: { label: 'Nötr bölge', tone: 'flat' },
  ABOVE_SIGNAL: { label: 'Sinyalin üstünde', tone: 'up' },
  BELOW_SIGNAL: { label: 'Sinyalin altında', tone: 'down' },
  TRENDING: { label: 'Trend güçlü', tone: 'warn' },
  WEAK_TREND: { label: 'Trend zayıf', tone: 'flat' },
  HIGH_VOLATILITY: { label: 'Yüksek oynaklık', tone: 'warn' },
  LOW_VOLATILITY: { label: 'Düşük oynaklık', tone: 'flat' },
  NORMAL_VOLATILITY: { label: 'Normal oynaklık', tone: 'flat' },
  POSITIVE: { label: 'Pozitif', tone: 'up' },
  NEGATIVE: { label: 'Negatif', tone: 'down' },
  ABOVE: { label: 'Üstünde', tone: 'up' },
  BELOW: { label: 'Altında', tone: 'down' },
};

/** Değeri ya da durumu `null` olan satır: gösterge henüz ısınıyor. */
export const WARMING_UP: Labeled = { label: 'Isınma dönemi; yeterli mum yok', tone: 'flat' };

/** Hareketli ortalama tablosu, `price_above_sma: true | false | null`. */
export const MA_POSITION: Record<'above' | 'below' | 'unknown', Labeled> = {
  above: { label: 'Fiyat üstünde', tone: 'up' },
  below: { label: 'Fiyat altında', tone: 'down' },
  unknown: { label: 'Veri yetersiz', tone: 'flat' },
};

export const maPosition = (priceAboveSma: boolean | null | undefined): Labeled =>
  priceAboveSma == null ? MA_POSITION.unknown : priceAboveSma ? MA_POSITION.above : MA_POSITION.below;

/* --- ikinci satır ----------------------------------------------------------- */

export type IndicatorExtra = Record<string, number | null | undefined>;

const decimals = (digits: number) =>
  new Intl.NumberFormat('tr-TR', { minimumFractionDigits: digits, maximumFractionDigits: digits });

/** tr-TR biçim, eksi işareti tipografik (−). */
const dec = (value: number, digits = 1) => decimals(digits).format(value).replace(/^-/, '−');

const finite = (extra: IndicatorExtra, name: string): number | null => {
  const value = extra[name];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
};

/**
 * Göstergenin yardımcı büyüklüklerini tek satıra çevirir; yoksa `null`.
 * ATR medyanı sunucudan dolar olarak gelir ve öyle yazılır; fiyat yüzdesine
 * çevirmek istemcide fiyat aritmetiği olurdu (DTO'da `median_pct` yok).
 * `key` DTO'da düz `string` geldiği için burada da öyle; tanınmayan anahtar `null` döner.
 */
export const indicatorExtraText = (key: IndicatorKey | string, extra: IndicatorExtra): string | null => {
  switch (key) {
    case 'stochastic': {
      const d = finite(extra, 'd');
      return d === null ? null : `%D ${dec(d)}`;
    }
    case 'macd': {
      const parts: string[] = [];
      const signal = finite(extra, 'signal');
      const histogram = finite(extra, 'histogram');
      if (signal !== null) parts.push(`Sinyal ${dec(signal)}`);
      if (histogram !== null) parts.push(`Histogram ${dec(histogram)}`);
      return parts.length ? parts.join(' · ') : null;
    }
    case 'adx': {
      const parts: string[] = [];
      const plus = finite(extra, 'plus_di');
      const minus = finite(extra, 'minus_di');
      if (plus !== null) parts.push(`+DI ${dec(plus)}`);
      if (minus !== null) parts.push(`−DI ${dec(minus)}`);
      return parts.length ? parts.join(' · ') : null;
    }
    case 'atr': {
      const median = finite(extra, 'median');
      return median === null ? null : `Medyan ${money2(median)}`;
    }
    default:
      return null;
  }
};
