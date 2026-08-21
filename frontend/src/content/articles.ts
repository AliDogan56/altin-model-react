import seoArticles from '../data/seo-articles.json';
import type { SeoArticle } from './types';

export const SEO_ARTICLES = seoArticles as SeoArticle[];

export const CATEGORY_ORDER = [...new Set(SEO_ARTICLES.map(a => a.category))];

export const GUIDES_BY_CATEGORY = CATEGORY_ORDER.map(
  category => [category, SEO_ARTICLES.filter(a => a.category === category)] as [string, SeoArticle[]],
);

export const articleById = (id: string): SeoArticle | undefined => SEO_ARTICLES.find(a => a.id === id);
