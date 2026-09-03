import articleIndex from '../data/articles-index.json';
import type { ArticleSummary, SeoArticle } from './types';

/**
 * Makale **indeksi**: gövdesiz, 4,5 KB gzip. Ana pakete yalnız bu girer.
 *
 * Tam veri (37 makale, 84 KB gzip) daha önce buradan statik olarak
 * içe aktarılıyordu ve anasayfaya gelen herkes 37 makalenin tam metnini
 * indiriyordu. Gövde artık iki yoldan gelir:
 *   1. Organik iniş: ön render edilen sayfaya gömülü JSON (ek istek yok).
 *   2. Uygulama içi gezinme: `loadArticle` ile tembel yüklenen tam veri.
 */
export const SEO_ARTICLES = articleIndex as ArticleSummary[];

export const CATEGORY_ORDER = [...new Set(SEO_ARTICLES.map(a => a.category))];

export const GUIDES_BY_CATEGORY = CATEGORY_ORDER.map(
  category => [category, SEO_ARTICLES.filter(a => a.category === category)] as [string, ArticleSummary[]],
);

export const summaryById = (id: string): ArticleSummary | undefined =>
  SEO_ARTICLES.find(a => a.id === id);

/** Ön render edilen sayfanın gövdeyi gömdüğü yer. */
const INLINE_ID = 'makale-verisi';

const inlineArticle = (id: string): SeoArticle | null => {
  if (typeof document === 'undefined') return null;
  const node = document.getElementById(INLINE_ID);
  if (!node?.textContent) return null;
  try {
    const parsed = JSON.parse(node.textContent) as SeoArticle;
    return parsed?.id === id ? parsed : null;
  } catch {
    return null;                       // bozuk gömülü veri sayfayı düşürmesin
  }
};

let tamVeri: Promise<SeoArticle[]> | null = null;

/**
 * Makalenin tam hâli. Sayfaya gömülüyse **eşzamanlı** döner — hidrasyonda
 * içeriğin bir an kaybolmasını önleyen kısım budur. Değilse tam veri bir kez
 * tembel yüklenir ve oturum boyunca yeniden istenmez.
 */
export const loadArticle = async (id: string): Promise<SeoArticle | null> => {
  const gomulu = inlineArticle(id);
  if (gomulu) return gomulu;
  tamVeri ??= import('../data/seo-articles.json').then(m => m.default as SeoArticle[]);
  return (await tamVeri).find(a => a.id === id) ?? null;
};

/** Yalnız gömülü veriyi okur; eşzamanlı ilk render için. */
export const articleFromPage = inlineArticle;
