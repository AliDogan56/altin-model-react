import { avg } from '../lib/math';
import type { Forecast } from './model/types';

export type TradeZones = {
  near: number; band: number; atr: number;
  buy: [number, number]; sell: [number, number];
  stop: number; entry: number; units: number;
};

/** Bir aylık tahmin ve bandından türeyen kademeli alım / kâr alma bölgeleri.
 *  Zarar kes, bandın ve ATR'nin büyüğüne göre kurulur; işlem önerisi değildir. */
export const tradeZones = (
  forecast: Forecast, price: number, atrPct: number, capital: number, riskPct: number,
): TradeZones => {
  const near = price * (1 + forecast.mean[1]);
  const band = price * forecast.err[1];
  const atr = atrPct * price;
  const buy: [number, number] = [near - band * .72, near - band * .38];
  const sell: [number, number] = [near + band * .35, near + band * .72];
  const stop = buy[0] - Math.max(atr * 1.5, band * .18);
  const entry = avg(buy);
  return { near, band, atr, buy, sell, stop, entry, units: (capital * riskPct / 100) / Math.max(1, entry - stop) };
};
