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
  const feature = featureBySlug(article.panel);
  return <main className="app article-page"><SiteNav current={article.id}/><article className="standalone-article">
    <nav className="breadcrumbs" aria-label="İçerik yolu"><Link to="/">Ana Sayfa</Link><span>/</span><Link to="/rehber">Altın Rehberi</Link><span>/</span><b>{article.title}</b></nav>
    <header id="icerik"><span className="eyebrow">{article.keyword}</span><h1>{article.title}</h1><p>{article.summary}</p></header>
    <div className="standalone-body">
      <p className="article-intro">{article.intro}</p>
      {feature && <p className="article-jump">
        <Link to={`/panel/${feature.slug}`}>{feature.title} <span aria-hidden="true">→</span></Link>
        <small>canlı veride, hesaplanmış hâliyle</small></p>}
      {article.sections.map((section)=><section key={section.heading}>
        <h2>{section.heading}</h2>
        {section.paragraphs.map((paragraph:string,i:number)=><p key={i}>{paragraph}</p>)}
        {section.list && (section.list.ordered
          ? <ol className="article-list">{section.list.items.map(item=><li key={item}>{item}</li>)}</ol>
          : <ul className="article-list">{section.list.items.map(item=><li key={item}>{item}</li>)}</ul>)}
        {section.table && <div className="article-table-wrap">
          <table className="article-table">
            <caption>{section.table.caption}</caption>
            <thead><tr>{section.table.columns.map(col=><th key={col} scope="col">{col}</th>)}</tr></thead>
            <tbody>{section.table.rows.map((row,i)=><tr key={i}>{row.map((cell,j)=>
              j===0 ? <th key={j} scope="row">{cell}</th> : <td key={j}>{cell}</td>)}</tr>)}</tbody>
          </table></div>}
      </section>)}
      <section className="article-summary"><h2>Özet: {article.keyword}</h2><ul>{article.points.map((point:string)=><li key={point}>{point}</li>)}</ul></section>
      <section className="article-faq"><h2>Sık sorulan sorular</h2>{article.faq.map((item)=><div key={item.q}><h3>{item.q}</h3><p>{item.a}</p></div>)}</section>
      {/* Yazı sonundaki geniş kart; üstteki kompakt link okumadan ayrılanı yakalar. */}
      {feature && <aside className="article-cta">
          <span className="article-cta-eyebrow">Bunu canlı veride gör</span>
          <b>{feature.title}</b>
          <p>{feature.summary}</p>
          <Link className="article-cta-link" to={`/panel/${feature.slug}`}>
            Panelde aç <span aria-hidden="true">→</span></Link>
        </aside>}
      <p className="article-updated"><small>Son güncelleme: {article.updated}</small></p>
    </div>
    <nav className="related-guides" aria-label="Diğer altın rehberleri"><h2>Diğer rehberler</h2><div>{SEO_ARTICLES.filter(item=>item.id!==article.id).slice(0,4).map(item=><Link to={`/rehber/${item.id}`} key={item.id}><small>{item.keyword}</small><b>{item.title}</b><span aria-hidden="true">→</span></Link>)}</div></nav>
  </article><SiteFooter/></main>;
}

export default ArticlePage;
