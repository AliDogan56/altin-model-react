import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { siteRoutes } from './site-routes.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const siteUrl = 'https://onsaltinanaliz.com';
const linkedInUrl = 'https://www.linkedin.com/in/ali-do%C4%9Fan-86b57721a/';

// Makale verisi tek bir JSON dosyasından okunur. Eskiden App.tsx string indeksiyle
// parse edilip Function() ile eval ediliyordu; kaynaktaki en küçük düzenleme build'i kırıyordu.
const articles = JSON.parse(await readFile(join(root, 'src/data/seo-articles.json'), 'utf8'));
const features = JSON.parse(await readFile(join(root, 'src/data/panel-features.json'), 'utf8'));
const sitePages = JSON.parse(await readFile(join(root, 'src/data/site-pages.json'), 'utf8'));
const rawBaseHtml = await readFile(join(root, 'dist/index.html'), 'utf8');
const today = new Date().toISOString().slice(0, 10);
const RELATED_COUNT = 5;
// Ön render edilen sayfalarda da tam uyarı bulunmalı: Google'ın indekslediği ve
// JavaScript çalışmadan görülen sürüm bunlar.
const LEGAL = `<section class="legal-note"><h2>Yasal uyarı ve sorumluluk reddi</h2>
        <p>Bu sitede yer alan bilgi, yorum, tahmin ve tavsiyeler <strong>yatırım danışmanlığı kapsamında değildir</strong>. Yatırım danışmanlığı hizmeti, yetkili kuruluşlar tarafından kişilerin risk ve getiri tercihleri dikkate alınarak kişiye özel sunulur. Buradaki içerik geneldir; mali durumunuza ve risk-getiri tercihlerinize uygun olmayabilir.</p>
        <p>Fiyat tahminleri geçmiş verilerden türetilmiş istatistiksel kestirimlerdir; kesinlik, isabet ya da kâr garantisi taşımaz. Veriler üçüncü taraf kaynaklardan alınır ve doğruluğu garanti edilmez; gösterge niteliğindedir.</p>
        <p>Bu platform hiçbir finansal ürün için alım-satım teklifi ya da çağrısı değildir. İçeriğe dayanarak alınan kararlardan ve doğabilecek doğrudan veya dolaylı zararlardan site sahibi sorumlu tutulamaz. Yatırım kararlarınızın sorumluluğu size aittir.</p>
        <nav aria-label="Site bilgileri"><a href="/hakkimizda">Hakkımızda</a> · <a href="/yazar">Yazar ve metodoloji</a> · <a href="/iletisim">İletişim</a> · <a href="/gizlilik">Gizlilik</a></nav></section>`;
const categories = [...new Set(articles.map(article => article.category))];
const byCategory = category => articles.filter(article => article.category === category);

/* `url` yazar sayfasına bakar: Article şemasının author'ı tıklanabilir bir
   kimliğe bağlanmadığında E-E-A-T sinyali zayıf kalıyor. */
const creator = {
  '@type': 'Person', '@id': `${siteUrl}/#creator`, name: 'Ali Doğan',
  url: `${siteUrl}/yazar`, mainEntityOfPage: `${siteUrl}/yazar`,
  sameAs: [linkedInUrl], jobTitle: 'Geliştirici ve içerik yazarı',
  knowsAbout: ['altın piyasası', 'XAU/USD', 'makroekonomik göstergeler', 'zaman serisi tahmini'],
};

const escapeHtml = value => String(value)
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#39;');

const jsonLd = value => `<script type="application/ld+json">${JSON.stringify(value).replaceAll('</script', '<\\/script')}</script>`;

const setMeta = (html, key, value, property = false) => {
  const attr = property ? 'property' : 'name';
  const pattern = new RegExp(`<meta\\s+${attr}="${key}"[^>]*>`, 'i');
  const tag = `<meta ${attr}="${key}" content="${escapeHtml(value)}" />`;
  return pattern.test(html) ? html.replace(pattern, tag) : html.replace('</head>', `    ${tag}\n  </head>`);
};
const replaceAttribute = (html, selector, attribute, value) => {
  const pattern = new RegExp(`(<${selector}[^>]*${attribute}=")[^"]*("[^>]*>)`, 'i');
  return html.replace(pattern, `$1${escapeHtml(value)}$2`);
};

// Anasayfadan devralınan ve makale sayfasında yanlış olan şemaları temizle.
const dropSchema = (html, type) => html.replace(
  new RegExp(`\\s*<script type="application/ld\\+json">\\s*\\{[^<]*?"@type":\\s*"${type}"[\\s\\S]*?</script>`, 'ig'), '');

/** Dönen pencere: her makale kendisinden sonraki N makaleye link verir.
 *  Eski slice(0,5) her zaman ilk beşi seçtiği için 15 sayfa hiç iç link almıyordu. */
const relatedOf = index => Array.from({ length: RELATED_COUNT },
  (_, offset) => articles[(index + offset + 1) % articles.length]);

/* Arama sonucundan gelen okuyucuyu konunun canlı karşılığına götürür.
   Ön render edilen sürümde de bulunmalı: Google'ın gördüğü ve JavaScript
   çalışmadan görünen HTML bu. */
const panelBySlug = new Map(features.map(feature => [feature.slug, feature]));
const panelJump = article => {
  const feature = panelBySlug.get(article.panel);
  return feature ? `<p class="article-jump"><a href="/panel/${escapeHtml(feature.slug)}">${escapeHtml(feature.title)} →</a> <small>canlı veride, hesaplanmış hâliyle</small></p>` : '';
};

const panelCta = article => {
  const feature = panelBySlug.get(article.panel);
  if (!feature) return '';
  return `<aside class="article-cta">
          <p>Bunu canlı veride gör</p>
          <h2>${escapeHtml(feature.title)}</h2>
          <p>${escapeHtml(feature.summary)}</p>
          <p><a class="article-cta-link" href="/panel/${escapeHtml(feature.slug)}">Panelde aç →</a></p>
        </aside>`;
};

/* Tablo ve liste blokları bot tarafından da görülmeli: ön render bunları
   React ile birebir aynı işaretlemeyle basar. */
const sectionHtml = section => `<section><h2>${escapeHtml(section.heading)}</h2>${
  section.paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join('')}${
  section.list ? `<${section.list.ordered ? 'ol' : 'ul'}>${section.list.items.map(i => `<li>${escapeHtml(i)}</li>`).join('')}</${section.list.ordered ? 'ol' : 'ul'}>` : ''}${
  section.table ? `<table><caption>${escapeHtml(section.table.caption)}</caption><thead><tr>${
    section.table.columns.map(c => `<th scope="col">${escapeHtml(c)}</th>`).join('')}</tr></thead><tbody>${
    section.table.rows.map(r => `<tr>${r.map((c, i) => i === 0
      ? `<th scope="row">${escapeHtml(c)}</th>` : `<td>${escapeHtml(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>` : ''}</section>`;

const articleBody = (article, related) => `<main class="seo-prerender" data-seo-page="${escapeHtml(article.id)}">
      <nav aria-label="İçerik yolu"><a href="/">Ana Sayfa</a> / <a href="/rehber">Altın Rehberi</a> / ${escapeHtml(article.title)}</nav>
      <article>
        <header><p>${escapeHtml(article.keyword)}</p><h1>${escapeHtml(article.title)}</h1><p>${escapeHtml(article.summary)}</p></header>
        <p>${escapeHtml(article.intro)}</p>
        ${panelJump(article)}
        ${article.sections.map(sectionHtml).join('\n        ')}
        <section><h2>Özet: ${escapeHtml(article.keyword)}</h2><ul>${article.points.map(point => `<li>${escapeHtml(point)}</li>`).join('')}</ul></section>
        <section><h2>Sık sorulan sorular</h2>${article.faq.map(item => `<h3>${escapeHtml(item.q)}</h3><p>${escapeHtml(item.a)}</p>`).join('')}</section>
        ${panelCta(article)}
        <p><small>Son güncelleme: ${escapeHtml(article.updated)}</small></p>
      </article>
      <nav aria-label="İlgili rehberler"><h2>İlgili Ons Altın Rehberleri</h2><ul>${related.map(item => `<li><a href="/rehber/${escapeHtml(item.id)}">${escapeHtml(item.title)}</a></li>`).join('')}</ul></nav>
      <footer>${LEGAL}<p>Projenin yaratıcısı: <a href="${linkedInUrl}" rel="me">Ali Doğan — LinkedIn</a></p><nav aria-label="Footer bağlantıları"><a href="/">Canlı ons paneli</a> · <a href="/#rehberler">Altın rehberleri</a> · <a href="/sitemap.xml">Sitemap</a></nav></footer>
    </main>`;

for (const [index, article] of articles.entries()) {
  const url = `${siteUrl}/rehber/${article.id}`;
  const title = `${article.seoTitle || article.title} | Ons Altın Analiz`;
  const related = relatedOf(index);
  const graph = [
    {
      '@type': 'Article', headline: article.title, description: article.summary,
      mainEntityOfPage: url, url, image: `${siteUrl}/social-preview-v1.png`,
      author: { '@id': `${siteUrl}/#creator` },
      publisher: { '@type': 'Organization', name: 'Ons Altın Analiz', url: siteUrl },
      datePublished: article.published || article.updated,
      dateModified: article.updated,        // build tarihi değil, içeriğin kendi tarihi
      inLanguage: 'tr-TR', articleSection: 'Ons Altın Rehberi', keywords: article.keyword
    },
    {
      '@type': 'FAQPage',
      mainEntity: article.faq.map(item => ({
        '@type': 'Question', name: item.q,
        acceptedAnswer: { '@type': 'Answer', text: item.a }
      }))
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Ana Sayfa', item: `${siteUrl}/` },
        { '@type': 'ListItem', position: 2, name: 'Altın Rehberi', item: `${siteUrl}/rehber` },
        { '@type': 'ListItem', position: 3, name: article.title, item: url }
      ]
    },
    creator
  ];

  let html = dropSchema(dropSchema(rawBaseHtml, 'ItemList'), 'WebApplication');
  html = html
    .replace(/<title>[^<]*<\/title>/i, `<title>${escapeHtml(title)}</title>`)
    .replace('<div id="root"></div>', `<div id="root">${articleBody(article, related)}</div>`)
    .replace('</head>', `    <meta property="article:section" content="Ons Altın Rehberi" />\n    <meta property="article:modified_time" content="${article.updated}" />\n    ${jsonLd({ '@context': 'https://schema.org', '@graph': graph })}\n  </head>`);
  html = replaceAttribute(html, 'link\\s+rel="canonical"', 'href', url);
  html = setMeta(html, 'description', article.summary);
  html = setMeta(html, 'keywords', `${article.keyword}, ons altın, altın analizi, altın fiyatları`);
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

/* ---- /panel/<slug> özellik sayfaları ----
   Her panel bölümünün kendi adresi var. Aynı içeriği 10 adreste sunmamak için her
   sayfa kendi başlığını, açıklamasını ve tanıtım metnini taşır; canonical kendine bakar. */
for (const [index, feature] of features.entries()) {
  const url = `${siteUrl}/panel/${feature.slug}`;
  const title = `${feature.seoTitle} | Ons Altın Analiz`;
  const others = features.filter(item => item.slug !== feature.slug).slice(0, 5);
  const fallback = `<main class="seo-prerender" data-seo-page="panel-${escapeHtml(feature.slug)}">
      <nav aria-label="İçerik yolu"><a href="/">Canlı Panel</a> / ${escapeHtml(feature.title)}</nav>
      <article>
        <header><h1>${escapeHtml(feature.title)}</h1><p>${escapeHtml(feature.summary)}</p></header>
        <p>${escapeHtml(feature.intro)}</p>
        <p><a href="/">Canlı panelde bu bölümü aç</a></p>
      </article>
      <nav aria-label="Diğer panel bölümleri"><h2>Panelin diğer bölümleri</h2><ul>${others.map(item => `<li><a href="/panel/${escapeHtml(item.slug)}">${escapeHtml(item.title)}</a></li>`).join('')}</ul></nav>
      <footer>${LEGAL}<nav aria-label="Footer bağlantıları"><a href="/">Canlı ons paneli</a> · <a href="/rehber">Altın rehberleri</a> · <a href="/sitemap.xml">Sitemap</a></nav></footer>
    </main>`;
  const schema = { '@context': 'https://schema.org', '@graph': [
    { '@type': 'WebPage', name: feature.title, description: feature.summary, url, inLanguage: 'tr-TR',
      isPartOf: { '@type': 'WebSite', url: siteUrl, name: 'Ons Altın Analiz' } },
    { '@type': 'BreadcrumbList', itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Canlı Panel', item: `${siteUrl}/` },
      { '@type': 'ListItem', position: 2, name: feature.title, item: url }] },
    creator] };
  let html = dropSchema(dropSchema(rawBaseHtml, 'ItemList'), 'WebApplication')
    .replace(/<title>[^<]*<\/title>/i, `<title>${escapeHtml(title)}</title>`)
    .replace('<div id="root"></div>', `<div id="root">${fallback}</div>`)
    .replace('</head>', `    ${jsonLd(schema)}\n  </head>`);
  html = replaceAttribute(html, 'link\\s+rel="canonical"', 'href', url);
  html = setMeta(html, 'description', feature.summary);
  html = setMeta(html, 'og:title', title, true);
  html = setMeta(html, 'og:description', feature.summary, true);
  html = setMeta(html, 'og:url', url, true);
  html = setMeta(html, 'twitter:title', title);
  html = setMeta(html, 'twitter:description', feature.summary);
  await mkdir(join(root, 'dist/panel', feature.slug), { recursive: true });
  await writeFile(join(root, 'dist/panel', feature.slug, 'index.html'), html);
}

/* ---- /panel dizin sayfası ----
   /panel daha önce 301 ile /panel/ adresine gidip 403 veriyordu (dizin listesi kapalı).
   Artık gerçek bir hedef sayfa; hem kullanıcı hem tarayıcı için tutarlı. */
const panelHubBody = `<main class="seo-prerender" data-seo-page="panel-hub">
      <nav aria-label="İçerik yolu"><a href="/">Canlı Panel</a> / Panel Bölümleri</nav>
      <header><h1>Panel Bölümleri</h1><p>Canlı ons altın panelinin ${features.length} bölümü; her biri kendi sayfasından da açılabilir.</p></header>
      <ul>${features.map(feature => `<li><a href="/panel/${escapeHtml(feature.slug)}"><strong>${escapeHtml(feature.title)}</strong></a> — ${escapeHtml(feature.summary)}</li>`).join('\n      ')}</ul>
      <footer>${LEGAL}<nav aria-label="Footer bağlantıları"><a href="/">Canlı ons paneli</a> · <a href="/rehber">Altın rehberleri</a> · <a href="/sitemap.xml">Sitemap</a></nav></footer>
    </main>`;
let panelHubHtml = dropSchema(dropSchema(rawBaseHtml, 'ItemList'), 'WebApplication')
  .replace(/<title>[^<]*<\/title>/i, '<title>Panel Bölümleri | Ons Altın Analiz</title>')
  .replace('<div id="root"></div>', `<div id="root">${panelHubBody}</div>`)
  .replace('</head>', `    ${jsonLd({ '@context': 'https://schema.org', '@graph': [
    { '@type': 'CollectionPage', name: 'Panel Bölümleri', url: `${siteUrl}/panel`,
      description: `Canlı ons altın panelinin ${features.length} bölümü.`, inLanguage: 'tr-TR',
      isPartOf: { '@type': 'WebSite', url: siteUrl, name: 'Ons Altın Analiz' } },
    { '@type': 'ItemList', numberOfItems: features.length,
      itemListElement: features.map((feature, index) => ({ '@type': 'ListItem', position: index + 1, name: feature.title, url: `${siteUrl}/panel/${feature.slug}` })) },
    creator] })}\n  </head>`);
panelHubHtml = replaceAttribute(panelHubHtml, 'link\\s+rel="canonical"', 'href', `${siteUrl}/panel`);
panelHubHtml = setMeta(panelHubHtml, 'description', `Canlı ons altın panelinin ${features.length} bölümü: tahmin, grafik, ziynet fiyatları, teknik göstergeler, pivot seviyeleri ve daha fazlası.`);
panelHubHtml = setMeta(panelHubHtml, 'og:title', 'Panel Bölümleri | Ons Altın Analiz', true);
panelHubHtml = setMeta(panelHubHtml, 'og:url', `${siteUrl}/panel`, true);
await mkdir(join(root, 'dist/panel'), { recursive: true });
await writeFile(join(root, 'dist/panel/index.html'), panelHubHtml);

/* ---- /rehber dizin sayfası ----
   Navbar'daki 31 kalemlik açılır liste yerine gerçek bir hedef sayfa; breadcrumb de buraya işaret eder. */
const hubBody = `<main class="seo-prerender" data-seo-page="hub">
      <nav aria-label="İçerik yolu"><a href="/">Ana Sayfa</a> / Altın Rehberi</nav>
      <header><h1>Ons Altın Rehberi</h1><p>Canlı fiyatı okumaktan model tahminlerini değerlendirmeye, gram ve ziynet altın hesabından alım satım pratiğine kadar ${articles.length} rehber; beş başlık altında toplandı.</p></header>
      ${categories.map(category => `<section><h2>${escapeHtml(category)}</h2><ul>${byCategory(category).map(article => `<li><a href="/rehber/${escapeHtml(article.id)}"><strong>${escapeHtml(article.title)}</strong></a> — ${escapeHtml(article.summary)}</li>`).join('')}</ul></section>`).join('\n      ')}
      <footer>${LEGAL}<nav aria-label="Footer bağlantıları"><a href="/">Canlı ons paneli</a> · <a href="/sitemap.xml">Sitemap</a></nav></footer>
    </main>`;

const hubSchema = { '@context': 'https://schema.org', '@graph': [
  { '@type': 'CollectionPage', name: 'Ons Altın Rehberi', url: `${siteUrl}/rehber`,
    description: `Ons altın, gram altın ve ziynet altın üzerine ${articles.length} rehber.`,
    inLanguage: 'tr-TR', isPartOf: { '@type': 'WebSite', url: siteUrl, name: 'Ons Altın Analiz' } },
  { '@type': 'ItemList', numberOfItems: articles.length,
    itemListElement: articles.map((article, index) => ({ '@type': 'ListItem', position: index + 1, name: article.title, url: `${siteUrl}/rehber/${article.id}` })) },
  { '@type': 'BreadcrumbList', itemListElement: [
    { '@type': 'ListItem', position: 1, name: 'Ana Sayfa', item: `${siteUrl}/` },
    { '@type': 'ListItem', position: 2, name: 'Altın Rehberi', item: `${siteUrl}/rehber` }] },
  creator] };

let hubHtml = dropSchema(dropSchema(rawBaseHtml, 'ItemList'), 'WebApplication')
  .replace(/<title>[^<]*<\/title>/i, '<title>Ons Altın Rehberi | Ons Altın Analiz</title>')
  .replace('<div id="root"></div>', `<div id="root">${hubBody}</div>`)
  .replace('</head>', `    ${jsonLd(hubSchema)}\n  </head>`);
hubHtml = replaceAttribute(hubHtml, 'link\\s+rel="canonical"', 'href', `${siteUrl}/rehber`);
hubHtml = setMeta(hubHtml, 'description', `Ons altın, gram altın ve ziynet altın üzerine ${articles.length} rehber; beş başlık altında derlendi.`);
hubHtml = setMeta(hubHtml, 'og:title', 'Ons Altın Rehberi | Ons Altın Analiz', true);
hubHtml = setMeta(hubHtml, 'og:url', `${siteUrl}/rehber`, true);
await mkdir(join(root, 'dist/rehber'), { recursive: true });
await writeFile(join(root, 'dist/rehber/index.html'), hubHtml);


/* ---- Anasayfa ön render ----
   Eskiden <div id="root"></div> boş gidiyordu: tarayıcıya h1 dahil hiçbir gövde
   ulaşmıyor, 31 rehbere giden iç linkler yalnız JS çalışınca oluşuyordu. */
const homeFallback = `<main class="seo-prerender" data-seo-page="home">
      <header><h1>Canlı Ons Altın Tahmin ve Senaryo Analiz Paneli</h1><p>Canlı ONS/XAUUSD fiyatı, reel faiz ve dolar endeksi gibi makro girdilerle beslenen 1 haftalık, 1 aylık ve 3 aylık altın tahminleriyle birlikte sunulur.</p><p>Tahmin, eğitim ve hata ölçümü doğrudan XAU/USD günlük serisine dayanır. Bu platform eğitim ve araştırma amaçlıdır, yatırım tavsiyesi değildir.</p></header>
      <section><h2>Panel bölümleri</h2><p>Panelin her bölümü kendi sayfasından da açılabilir.</p>
        <ul>${features.map(feature => `<li><a href="/panel/${escapeHtml(feature.slug)}"><strong>${escapeHtml(feature.title)}</strong></a> — ${escapeHtml(feature.summary)}</li>`).join('\n        ')}</ul>
      </section>
      <section id="rehberler"><h2>Ons Altın Analizi ve Tahmin Rehberleri</h2><p>Canlı fiyatı doğru okumak, modeli değerlendirmek ve altını etkileyen ekonomik göstergeleri anlamak için hazırlanan ${articles.length} rehber. Tümü <a href="/rehber">Altın Rehberi</a> sayfasında.</p>
        ${categories.map(category => `<section><h3>${escapeHtml(category)}</h3><ul>${byCategory(category).map(article => `<li><a href="/rehber/${escapeHtml(article.id)}"><strong>${escapeHtml(article.title)}</strong></a> — ${escapeHtml(article.summary)}</li>`).join('')}</ul></section>`).join('\n        ')}
      </section>
      <footer>${LEGAL}<p>Projenin yaratıcısı: <a href="${linkedInUrl}" rel="me">Ali Doğan — LinkedIn</a></p><nav aria-label="Footer bağlantıları"><a href="/sitemap.xml">Sitemap</a></nav></footer>
    </main>`;

const homeItemList = {
  '@context': 'https://schema.org', '@type': 'ItemList',
  name: 'Ons Altın Analizi ve Tahmin Rehberleri', numberOfItems: articles.length,
  itemListElement: articles.map((article, index) => ({
    '@type': 'ListItem', position: index + 1, name: article.title, url: `${siteUrl}/rehber/${article.id}`
  }))
};
const homeHtml = dropSchema(rawBaseHtml, 'ItemList')
  .replace('<div id="root"></div>', `<div id="root">${homeFallback}</div>`)
  .replace('</head>', `    ${jsonLd(homeItemList)}\n    ${jsonLd({ '@context': 'https://schema.org', ...creator })}\n  </head>`);

/* Kurumsal sayfalar da ön render edilir: YMYL kategorisinde Google'ın
   güven sinyali aradığı sayfalar bunlar ve JavaScript'siz görünmeleri gerekir. */
const sitePageBody = page => `<main class="seo-prerender" data-seo-page="${escapeHtml(page.slug)}">
      <nav aria-label="İçerik yolu"><a href="/">Ana Sayfa</a> / ${escapeHtml(page.title)}</nav>
      <article>
        <header><h1>${escapeHtml(page.title)}</h1><p>${escapeHtml(page.summary)}</p></header>
        ${page.sections.map(section => `<section><h2>${escapeHtml(section.heading)}</h2>${section.paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join('')}</section>`).join('\n        ')}
        <p><small>Son güncelleme: ${escapeHtml(page.updated)}</small></p>
      </article>
      <nav aria-label="Diğer sayfalar"><h2>Diğer sayfalar</h2><ul>${sitePages.filter(other => other.slug !== page.slug).map(other => `<li><a href="/${escapeHtml(other.slug)}">${escapeHtml(other.title)}</a></li>`).join('')}</ul></nav>
      <footer>${LEGAL}<nav aria-label="Footer bağlantıları"><a href="/">Canlı ons paneli</a> · <a href="/rehber">Altın rehberleri</a> · <a href="/sitemap.xml">Sitemap</a></nav></footer>
    </main>`;

for (const page of sitePages) {
  const url = `${siteUrl}/${page.slug}`;
  const title = `${page.seoTitle} | Ons Altın Analiz`;
  let html = dropSchema(dropSchema(rawBaseHtml, 'ItemList'), 'FAQPage');
  html = setMeta(html, 'description', page.summary);
  html = setMeta(html, 'og:title', title, true);
  html = setMeta(html, 'og:description', page.summary, true);
  html = setMeta(html, 'og:url', url, true);
  html = setMeta(html, 'twitter:title', title);
  html = setMeta(html, 'twitter:description', page.summary);
  html = html.replace(/<title>.*?<\/title>/, `<title>${escapeHtml(title)}</title>`);
  html = replaceAttribute(html, 'link rel="canonical"', 'href', url);
  html = html.replace('</head>', `    ${jsonLd({
    '@context': 'https://schema.org',
    '@graph': [
      { '@type': 'WebPage', '@id': url, url, name: title, description: page.summary,
        dateModified: page.updated, inLanguage: 'tr-TR', author: { '@id': `${siteUrl}/#creator` } },
      { '@type': 'BreadcrumbList', itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Ana Sayfa', item: `${siteUrl}/` },
        { '@type': 'ListItem', position: 2, name: page.title, item: url },
      ] },
      creator,
    ],
  })}\n  </head>`);
  html = html.replace('<div id="root"></div>', `<div id="root">${sitePageBody(page)}</div>`);
  await mkdir(join(root, 'dist', page.slug), { recursive: true });
  await writeFile(join(root, 'dist', page.slug, 'index.html'), html);
}

const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${(await siteRoutes(today)).map(route => `  <url><loc>${siteUrl}${route.path}</loc><lastmod>${route.lastmod}</lastmod><changefreq>${route.changefreq}</changefreq><priority>${route.priority}</priority></url>`).join('\n')}
</urlset>
`;

await writeFile(join(root, 'dist/index.html'), homeHtml);
await writeFile(join(root, 'dist/sitemap.xml'), sitemap);
console.log(`${articles.length} rehber + dizin + ${features.length} panel + ${sitePages.length} kurumsal sayfa, ön render edilmiş anasayfa ve sitemap oluşturuldu.`);
