import { describe, expect, it } from 'vitest';
import kaynak from '../data/seo-articles.json';
import indeks from '../data/articles-index.json';
import { SEO_ARTICLES } from './articles';

/* İndeks üretilmiş bir dosya (`scripts/build-article-index.mjs`) ve depoya
   işleniyor ki `vite dev` ön adım gerektirmesin. Bedeli: kaynak değişip indeks
   yeniden üretilmezse ikisi ayrışır. Bu testler o ayrışmayı yakalar. */
describe('makale indeksi', () => {
  it('kaynakla aynı makaleleri aynı sırada taşır', () => {
    expect(indeks.map(a => a.id)).toEqual(kaynak.map(a => a.id));
  });

  it('özet alanları kaynakla birebir aynı', () => {
    const alanlar = ['id', 'keyword', 'title', 'seoTitle', 'summary',
      'category', 'updated', 'panel'] as const;
    kaynak.forEach((tam, i) => {
      const ozet = indeks[i] as Record<string, unknown>;
      alanlar.forEach(alan => {
        if (alan in tam) expect(ozet[alan]).toBe((tam as Record<string, unknown>)[alan]);
      });
    });
  });

  /* Asıl amaç buydu: gövde ana pakete girmemeli. */
  it('indeks gövde taşımaz', () => {
    const govde = ['sections', 'faq', 'points', 'intro'];
    indeks.forEach(a => govde.forEach(k => expect(k in a).toBe(false)));
  });

  it('indeks kaynaktan belirgin biçimde küçüktür', () => {
    const boyut = (x: unknown) => JSON.stringify(x).length;
    expect(boyut(indeks)).toBeLessThan(boyut(kaynak) / 10);
  });

  it('SEO_ARTICLES indeksten beslenir', () => {
    expect(SEO_ARTICLES).toHaveLength(kaynak.length);
    expect('sections' in (SEO_ARTICLES[0] as object)).toBe(false);
  });
});
