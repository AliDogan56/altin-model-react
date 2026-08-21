import { avg, std } from '../../lib/math';
import type { FeatureMap } from '../model/types';

export type Ohlc = { close: number[]; high: number[]; low: number[]; volume: number[] };

/** Günlük mumlardan modelin teknik girdilerini üretir. Oranlar ondalık (0.02 = %2). */
export const goldFeatures = ({ close, high, low, volume }: Ohlc): FeatureMap => {
  const last = close.length - 1;
  const ret = (n: number) => close[last] / close[last - n] - 1;
  const ma = (n: number) => avg(close.slice(-n));
  const f: FeatureMap = {
    gold_return_1d: ret(1), gold_return_5d: ret(5), gold_return_20d: ret(20), gold_return_60d: ret(60),
    gold_ma_ratio_20d: close[last] / ma(20) - 1,
    gold_ma_ratio_50d: close[last] / ma(50) - 1,
    gold_ma_ratio_200d: close[last] / ma(200) - 1,
  };

  const diff = close.slice(1).map((v, i) => v - close[i]);
  const gains = diff.slice(-14).map(v => Math.max(0, v));
  const losses = diff.slice(-14).map(v => Math.max(0, -v));
  f.gold_rsi14 = 100 - 100 / (1 + avg(gains) / (avg(losses) || 1e-9));

  const tr = close.slice(1).map((_, i) =>
    Math.max(high[i + 1] - low[i + 1], Math.abs(high[i + 1] - close[i]), Math.abs(low[i + 1] - close[i])));
  f.gold_atr14_pct = avg(tr.slice(-14)) / close[last];

  const logReturns = close.slice(1).map((v, i) => Math.log(v / close[i]));
  f.gold_volatility_20d = std(logReturns.slice(-20)) * Math.sqrt(365);

  const logVol = volume.map(v => Math.log1p(v));
  f.gold_volume_z20 = (logVol[last] - avg(logVol.slice(-20))) / (std(logVol.slice(-20)) || 1);
  return f;
};
