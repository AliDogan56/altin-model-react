import { Link } from 'react-router-dom';
import { useEffect } from 'react';
import SiteNav from '../components/SiteNav';
import SiteFooter from '../components/SiteFooter';
import { SEO_ARTICLES } from '../content/articles';
import { featureBySlug } from '../content/panel';
import type { SeoArticle } from '../content/types';


function ArticlePage({article}:{article:SeoArticle}) {
  useEffect(()=>{
    const url=`${window.location.origin}/rehber/${article.id}`;
    const title=`${article.seoTitle||article.title} | Ons Altın Analiz`;
    document.title=title;
    const set=(selector:string,value:string,attribute='content')=>{const node=document.querySelector(selector);if(node)node.setAttribute(attribute,value);};
    set('meta[name="description"]',article.summary);
    set('link[rel="canonical"]',url,'href');
    set('meta[property="og:title"]',title);
    set('meta[property="og:description"]',article.summary);
    set('meta[property="og:url"]',url);
    set('meta[name="twitter:title"]',title);
    set('meta[name="twitter:description"]',article.summary);
  },[article]);
  return <main className="app article-page"><SiteNav current={article.id}/><article className="standalone-article">
    <nav className="breadcrumbs" aria-label="İçerik yolu"><Link to="/">Ana Sayfa</Link><span>/</span><Link to="/rehber">Altın Rehberi</Link><span>/</span><b>{article.title}</b></nav>
    <header id="icerik"><span className="eyebrow">{article.keyword}</span><h1>{article.title}</h1><p>{article.summary}</p></header>
    <div className="standalone-body">
      <p className="article-intro">{article.intro}</p>
      {article.sections.map((section)=><section key={section.heading}><h2>{section.heading}</h2>{section.paragraphs.map((paragraph:string,i:number)=><p key={i}>{paragraph}</p>)}</section>)}
      <section className="article-summary"><h2>Özet: {article.keyword}</h2><ul>{article.points.map((point:string)=><li key={point}>{point}</li>)}</ul></section>
      <section className="article-faq"><h2>Sık sorulan sorular</h2>{article.faq.map((item)=><div key={item.q}><h3>{item.q}</h3><p>{item.a}</p></div>)}</section>
      {(() => {
        /* Arama sonucundan gelen okuyucu, konunun canlı karşılığını göremeden
           sayfadan çıkıyordu; panelde ilgili bölüm açılıp vurgulanıyor. */
        const feature = featureBySlug(article.panel);
        return feature && <aside className="article-cta">
          <span className="article-cta-eyebrow">Bunu canlı veride gör</span>
          <b>{feature.title}</b>
          <p>{feature.summary}</p>
          <Link className="article-cta-link" to={`/panel/${feature.slug}`}>
            Panelde aç <span aria-hidden="true">→</span></Link>
        </aside>;
      })()}
      <p className="article-updated"><small>Son güncelleme: {article.updated}</small></p>
    </div>
    <nav className="related-guides" aria-label="Diğer altın rehberleri"><h2>Diğer rehberler</h2><div>{SEO_ARTICLES.filter(item=>item.id!==article.id).slice(0,4).map(item=><Link to={`/rehber/${item.id}`} key={item.id}><small>{item.keyword}</small><b>{item.title}</b><span aria-hidden="true">→</span></Link>)}</div></nav>
  </article><SiteFooter/></main>;
}

export default ArticlePage;
