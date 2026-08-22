import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

/** Sitemap ve React Router aynı listeden beslenir; ikisi ayrı yazıldığında
 *  eklenen bir sayfa sitemap'e girip rotaya girmiyordu (ya da tersi).
 *  src/app/routes.ts aynı JSON'lardan aynı yolları üretir, routes.test.ts eşitliği doğrular. */
export const siteRoutes = async (today = new Date().toISOString().slice(0, 10)) => {
  const read = async name => JSON.parse(await readFile(join(root, 'src/data', name), 'utf8'));
  const articles = await read('seo-articles.json');
  const features = await read('panel-features.json');
  const pages = await read('site-pages.json');
  return [
    { path: '/', lastmod: today, changefreq: 'daily', priority: '1.0' },
    { path: '/rehber', lastmod: today, changefreq: 'weekly', priority: '0.9' },
    { path: '/panel', lastmod: today, changefreq: 'weekly', priority: '0.9' },
    ...features.map(f => ({ path: `/panel/${f.slug}`, lastmod: today, changefreq: 'daily', priority: '0.8' })),
    ...articles.map(a => ({ path: `/rehber/${a.id}`, lastmod: a.updated, changefreq: 'monthly', priority: '0.8' })),
    ...pages.map(p => ({ path: `/${p.slug}`, lastmod: p.updated, changefreq: 'yearly', priority: p.priority })),
  ];
};
