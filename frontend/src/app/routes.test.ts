import { describe, expect, it } from 'vitest';
// @ts-expect-error — .mjs modülü; tipleri scripts/site-routes.d.ts içinde
import { siteRoutes } from '../../scripts/site-routes.mjs';
import { SITE_ROUTES } from './routes';

describe('rota tablosu', () => {
  it('sitemap ile aynı yolları üretir', async () => {
    const sitemap = (await siteRoutes()).map((route: { path: string }) => route.path);
    expect(SITE_ROUTES.map(r => r.path)).toEqual(sitemap);
  });

  it('yollar benzersizdir', () => {
    expect(new Set(SITE_ROUTES.map(r => r.path)).size).toBe(SITE_ROUTES.length);
  });

  it('her yol tek eğik çizgiyle başlar ve sonda eğik çizgi yoktur', () => {
    SITE_ROUTES.slice(1).forEach(r => {
      expect(r.path).toMatch(/^\/[a-z0-9-]+(\/[a-z0-9-]+)?$/);
    });
  });
});
