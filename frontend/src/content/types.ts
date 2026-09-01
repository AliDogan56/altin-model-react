export type SeoSection = {
  heading: string; paragraphs: string[];
  table?: SeoTable; list?: SeoList;
};
export type SeoFaq = { q: string; a: string };
/** Bölüm içi tablo: "kaç gram", "hangi seviye" gibi sayısal içerikte
    düz paragraftan hem okunur hem taranabilir olarak daha iyi. */
export type SeoTable = { caption: string; columns: string[]; rows: string[][] };
export type SeoList = { ordered?: boolean; items: string[] };

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
  /**
   * Panel sayfasının kendi anlatısı. **Dizine girmenin koşulu budur:**
   * `/panel/<slug>` React'te panonun kendisini render ettiği için bölümsüz bir
   * panel sayfası, 11 URL'de aynı panoyu gösteren bir kopya olur ve Google
   * onu indekslemez (28 Ağustos 2026 Coverage raporunda 11 panel URL'inin
   * 11'i de dizin dışıydı). Bölüm taşıyan panel hem ön render'da hem
   * uygulamada kendi metnini gösterir; taşımayan `noindex` alır ve sitemap'e
   * girmez — `scripts/site-routes.mjs` bu alana bakar.
   */
  sections?: SeoSection[];
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
