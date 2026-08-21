import type { Candle } from '../../domain/indicators';
import { parseCsv, type SeriesPoint } from '../../lib/series';
import { MARKET_API } from '../config';
import { fetchJson, fetchText } from '../http';

/** Binance kline dizisi: [openTime, open, high, low, close, volume, ...] */
export type Kline = [number, string, string, string, string, string, ...unknown[]];

export type Spot = { lastPrice: string; priceChangePercent: string };

export type NewsArticle = { title: string; url: string; source?: string; published?: string };

export const fetchKlines = () => fetchJson<Kline[]>(`${MARKET_API}/v1/market/binance`);

export const fetchSpot = () => fetchJson<Spot>(`${MARKET_API}/v1/market/spot`);

export const fetchNews = async (): Promise<NewsArticle[]> =>
  (await fetchJson<{ articles?: NewsArticle[] }>(`${MARKET_API}/v1/market/news`)).articles || [];

export const fetchFred = async (id: string): Promise<SeriesPoint[]> =>
  parseCsv(await fetchText(`${MARKET_API}/v1/market/fred?id=${id}`));

export const fetchFredSet = async (ids: readonly string[]): Promise<Record<string, SeriesPoint[]>> =>
  Object.fromEntries(await Promise.all(ids.map(async id => [id, await fetchFred(id)] as const)));

export const toCandles = (klines: Kline[]): Candle[] =>
  klines.map(v => ({ date: new Date(v[0]).toISOString().slice(0, 10), h: +v[2], l: +v[3], c: +v[4] }));

export const toHistory = (klines: Kline[]): [string, number][] =>
  klines.map(v => [new Date(v[0]).toISOString().slice(0, 10), +v[4]]);
