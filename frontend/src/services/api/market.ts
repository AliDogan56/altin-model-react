import { marketApi } from '../config';
import { fetchJson } from '../http';

export type NewsArticle = { title: string; url: string; source?: string; published?: string };

/* Günlük fiyat serisi (`/v1/market/xau`) artık buradan çekilmiyor: teknik paket
   (`services/api/technical.ts`) aynı seriyi `daily.candles` olarak taşıyor. */

export const fetchNews = async (): Promise<NewsArticle[]> =>
  (await fetchJson<{ articles?: NewsArticle[] }>(`${marketApi()}/v1/market/news`)).articles || [];
