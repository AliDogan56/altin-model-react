export type SitemapRoute = { path: string; lastmod: string; changefreq: string; priority: string };
/** Sitemap ve React Router aynı listeden beslenir; routes.test.ts eşitliği doğrular. */
export declare const siteRoutes: (today?: string) => Promise<SitemapRoute[]>;
