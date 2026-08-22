import { SEO_ARTICLES } from '../content/articles';
import { PANEL_FEATURES } from '../content/panel';
import { SITE_PAGES } from '../content/pages';

export type RouteKind = 'dashboard' | 'panel-hub' | 'panel-feature' | 'guide-hub' | 'guide' | 'page';

export type SiteRoute = { path: string; kind: RouteKind };

/** Uygulamanın gezinebildiği tüm yollar. scripts/site-routes.mjs sitemap'i aynı
 *  JSON'lardan üretir; routes.test.ts iki listenin birebir aynı olduğunu doğrular. */
export const SITE_ROUTES: SiteRoute[] = [
  { path: '/', kind: 'dashboard' },
  { path: '/rehber', kind: 'guide-hub' },
  { path: '/panel', kind: 'panel-hub' },
  ...PANEL_FEATURES.map(f => ({ path: `/panel/${f.slug}`, kind: 'panel-feature' as const })),
  ...SEO_ARTICLES.map(a => ({ path: `/rehber/${a.id}`, kind: 'guide' as const })),
  ...SITE_PAGES.map(p => ({ path: `/${p.slug}`, kind: 'page' as const })),
];
