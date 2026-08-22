import { marketApi } from '../config';
import { fetchJson } from '../http';

export type NewsArticle = { title: string; url: string; source?: string; published?: string };
export type XauPoint = { d: string; c: number; h: number; l: number };

export const fetchXauHistory = async () =>
  (await fetchJson<{ points: XauPoint[] }>(`${marketApi()}/v1/market/xau`)).points;

export const fetchNews = async (): Promise<NewsArticle[]> =>
  (await fetchJson<{ articles?: NewsArticle[] }>(`${marketApi()}/v1/market/news`)).articles || [];

