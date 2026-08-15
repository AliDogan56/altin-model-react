import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const siteUrl = 'https://onsaltinanaliz.com';
const source = await readFile(join(root, 'src/App.tsx'), 'utf8');
const startMarker = 'const SEO_ARTICLES = [';
const endMarker = '\n];\nconst avg';
const start = source.indexOf(startMarker);
const end = source.indexOf(endMarker, start);

if (start < 0 || end < 0) {
  throw new Error('SEO_ARTICLES listesi App.tsx içinde bulunamadı.');
}

const literal = source.slice(start + 'const SEO_ARTICLES = '.length, end + 2);
const articles = Function(`"use strict"; return (${literal});`)();
const rawBaseHtml = await readFile(join(root, 'dist/index.html'), 'utf8');
const today = new Date().toISOString().slice(0, 10);
const linkedInUrl = 'https://www.linkedin.com/in/ali-do%C4%9Fan-86b57721a/';
const creator = {
  '@type': 'Person',
  '@id': `${siteUrl}/#creator`,
  name: 'Ali Doğan',
  url: siteUrl,
  sameAs: [linkedInUrl],
  jobTitle: 'Yaratıcı ve geliştirici'
};
const itemListPattern = /\s*<script type="application\/ld\+json">\s*\{\s*"@context":\s*"https:\/\/schema\.org",\s*"@type":\s*"ItemList"[\s\S]*?<\/script>/i;
const baseHtml = rawBaseHtml.replace(itemListPattern, '');

const escapeHtml = value => String(value)
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;');

const replaceAttribute = (html, selector, attribute, value) => {
  const escaped = escapeHtml(value);
  const pattern = new RegExp(`(<${selector}[^>]*${attribute}=")[^"]*("[^>]*>)`, 'i');
  return html.replace(pattern, `$1${escaped}$2`);
};

const setMeta = (html, key, value, property = false) => {
  const attr = property ? 'property' : 'name';
  const pattern = new RegExp(`<meta\\s+${attr}="${key}"[^>]*>`, 'i');
  const tag = `<meta ${attr}="${key}" content="${escapeHtml(value)}" />`;
  return pattern.test(html) ? html.replace(pattern, tag) : html.replace('</head>', `    ${tag}\n  </head>`);
};

for (const article of articles) {
  const url = `${siteUrl}/rehber/${article.id}`;
  const title = `${article.title} | Ons Altın Analiz`;
  const keywords = `${article.keyword}, ons altın, altın analizi, altın fiyatları`;
  const related = articles.filter(item => item.id !== article.id).slice(0, 5);
  const structuredData = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Article',
        headline: article.title,
        description: article.summary,
        mainEntityOfPage: url,
        url,
        image: `${siteUrl}/social-preview-v1.png`,
        author: { '@id': `${siteUrl}/#creator` },
        publisher: { '@type': 'Organization', name: 'Ons Altın Analiz', url: siteUrl },
        datePublished: today,
        dateModified: today,
        inLanguage: 'tr-TR',
        articleSection: 'Ons Altın Rehberi',
        keywords: article.keyword
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Ana Sayfa', item: `${siteUrl}/` },
          { '@type': 'ListItem', position: 2, name: 'Altın Rehberi', item: `${siteUrl}/#rehberler` },
          { '@type': 'ListItem', position: 3, name: article.title, item: url }
        ]
      },
      creator
    ]
  };
  const fallback = `<main class="seo-prerender" data-seo-page="${escapeHtml(article.id)}">
      <nav aria-label="İçerik yolu"><a href="/">Ana Sayfa</a> / <a href="/#rehberler">Altın Rehberi</a> / ${escapeHtml(article.title)}</nav>
      <article>
        <header><p>${escapeHtml(article.keyword)}</p><h1>${escapeHtml(article.title)}</h1><p>${escapeHtml(article.summary)}</p></header>
        ${article.paragraphs.map(paragraph => `<p>${escapeHtml(paragraph)}</p>`).join('\n        ')}
        <section><h2>${escapeHtml(article.title)}: Kısa Notlar</h2><ul>${article.points.map(point => `<li>${escapeHtml(point)}</li>`).join('')}</ul></section>
      </article>
      <nav aria-label="İlgili rehberler"><h2>İlgili Ons Altın Rehberleri</h2><ul>${related.map(item => `<li><a href="/rehber/${escapeHtml(item.id)}">${escapeHtml(item.title)}</a></li>`).join('')}</ul></nav>
      <footer><p>Bu platform eğitim ve araştırma amaçlıdır; kişisel yatırım tavsiyesi değildir.</p><p>Projenin yaratıcısı: <a href="${linkedInUrl}" rel="me">Ali Doğan — LinkedIn</a></p><nav aria-label="Footer bağlantıları"><a href="/">Canlı ons paneli</a> · <a href="/#rehberler">Altın rehberleri</a> · <a href="/sitemap.xml">Sitemap</a></nav></footer>
    </main>`;

  let html = baseHtml
    .replace(/<title>[^<]*<\/title>/i, `<title>${escapeHtml(title)}</title>`)
    .replace('<div id="root"></div>', `<div id="root">${fallback}</div>`)
    .replace('</head>', `    <meta property="article:section" content="Ons Altın Rehberi" />\n    <meta property="article:modified_time" content="${today}" />\n    <script type="application/ld+json">${JSON.stringify(structuredData).replaceAll('</script', '<\\/script')}</script>\n  </head>`);
  html = replaceAttribute(html, 'link\\s+rel="canonical"', 'href', url);
  html = setMeta(html, 'description', article.summary);
  html = setMeta(html, 'keywords', keywords);
  html = setMeta(html, 'og:type', 'article', true);
  html = setMeta(html, 'og:title', title, true);
  html = setMeta(html, 'og:description', article.summary, true);
  html = setMeta(html, 'og:url', url, true);
  html = setMeta(html, 'twitter:title', title);
  html = setMeta(html, 'twitter:description', article.summary);

  const output = join(root, 'dist/rehber', article.id, 'index.html');
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, html);
}

const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>${siteUrl}/</loc><lastmod>${today}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>
${articles.map(article => `  <url><loc>${siteUrl}/rehber/${article.id}</loc><lastmod>${today}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>`).join('\n')}
</urlset>
`;
const homeItemList = {
  '@context': 'https://schema.org',
  '@type': 'ItemList',
  name: 'Ons Altın Analizi ve Tahmin Rehberleri',
  numberOfItems: articles.length,
  itemListElement: articles.map((article, index) => ({
    '@type': 'ListItem',
    position: index + 1,
    name: article.title,
    url: `${siteUrl}/rehber/${article.id}`
  }))
};
const creatorScript = `<script type="application/ld+json">${JSON.stringify({ '@context': 'https://schema.org', ...creator }).replaceAll('</script', '<\\/script')}</script>`;
const homeHtml = rawBaseHtml.replace(itemListPattern, `\n    <script type="application/ld+json">${JSON.stringify(homeItemList).replaceAll('</script', '<\\/script')}</script>`).replace('</head>', `    ${creatorScript}\n  </head>`);
await writeFile(join(root, 'dist/index.html'), homeHtml);
await writeFile(join(root, 'dist/sitemap.xml'), sitemap);
console.log(`${articles.length} statik SEO sayfası ve sitemap oluşturuldu.`);
