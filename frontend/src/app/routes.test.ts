import { describe, expect, it } from 'vitest';
// @ts-expect-error — .mjs modülü; tipleri scripts/site-routes.d.ts içinde
import { siteRoutes } from '../../scripts/site-routes.mjs';
import { PANEL_FEATURES } from '../content/panel';
import { SITE_ROUTES } from './routes';

describe('rota tablosu', () => {
  /* Sitemap artık uygulama rotalarının bir **alt kümesi**: içerik taşımayan
     panel sayfaları rotada var ama sitemap'te yok (yinelenen içerik oldukları
     için). Ters yön hâlâ hata: sitemap'te olup rotada olmayan yol 404 verir. */
  it('sitemapteki her yol uygulamada da tanımlı', async () => {
    const sitemap = (await siteRoutes()).map((route: { path: string }) => route.path);
    const rotalar = new Set(SITE_ROUTES.map(r => r.path));
    expect(sitemap.filter((path: string) => !rotalar.has(path))).toEqual([]);
  });

  it('sitemap yalnız anlatısı olan panel sayfalarını listeler', async () => {
    const sitemap = (await siteRoutes()).map((route: { path: string }) => route.path);
    const panelYollari = sitemap.filter((path: string) => path.startsWith('/panel/'));
    const anlatili = PANEL_FEATURES.filter(f => f.sections?.length).map(f => `/panel/${f.slug}`);
    expect(panelYollari.sort()).toEqual(anlatili.sort());
    // Hepsi rotada durmaya devam eder; yalnız sitemap dışıdırlar.
    PANEL_FEATURES.forEach(f =>
      expect(SITE_ROUTES.some(r => r.path === `/panel/${f.slug}`)).toBe(true));
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
