export type SeoSection = { heading: string; paragraphs: string[] };
export type SeoFaq = { q: string; a: string };
export type SeoArticle = {
  id: string; keyword: string; title: string; seoTitle?: string; updated: string;
  summary: string; intro: string; category: string;
  sections: SeoSection[]; points: string[]; faq: SeoFaq[];
};

export type PanelFeature = {
  slug: string; anchor: string; collapsible: boolean;
  title: string; seoTitle: string; summary: string; intro: string;
};

export type ParameterItem = [id: string, label: string, unit: string];
export type ParameterGroup = [title: string, items: ParameterItem[]];
