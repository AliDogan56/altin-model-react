import sitePages from '../data/site-pages.json';
import type { SitePage } from './types';

/** Kurumsal / güven sayfaları. YMYL kategorisinde Google bunları arar;
 *  öncesinde site hiçbirine sahip değildi. */
export const SITE_PAGES = sitePages as SitePage[];

export const pageBySlug = (slug: string): SitePage | undefined =>
  SITE_PAGES.find(page => page.slug === slug);
