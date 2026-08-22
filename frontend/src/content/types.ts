export type SeoSection = { heading: string; paragraphs: string[] };
export type SeoFaq = { q: string; a: string };
export type SeoArticle = {
  id: string; keyword: string; title: string; seoTitle?: string; updated: string;
  summary: string; intro: string; category: string;
  sections: SeoSection[]; points: string[]; faq: SeoFaq[];
  /** Makalenin canlı karşılığı olan panel bölümünün slug'ı. */
  panel: string;
};

export type PanelFeature = {
  slug: string; anchor: string; collapsible: boolean;
  title: string; seoTitle: string; summary: string; intro: string;
};

export type ParameterItem = [id: string, label: string, unit: string];
export type ParameterGroup = [title: string, items: ParameterItem[]];

export type SitePageSection = { heading: string; paragraphs: string[] };

/** Hakkımızda, yazar, iletişim, gizlilik gibi kurumsal sayfalar. */
export type SitePage = {
  slug: string; title: string; seoTitle: string; summary: string;
  updated: string; priority: string;
  sections: SitePageSection[];
};
