import { Link } from 'react-router-dom';
import SiteNav from '../components/SiteNav';
import SiteFooter from '../components/SiteFooter';
import { GUIDES_BY_CATEGORY, SEO_ARTICLES } from '../content/articles';
import { PAGE_META } from '../content/site';
import { useDocumentMeta } from '../app/useDocumentMeta';

function GuideHub() {
  useDocumentMeta(PAGE_META.guides.title, PAGE_META.guides.description, PAGE_META.guides.path);
  return <main className="app article-page"><SiteNav/>
    <article className="standalone-article guide-hub">
      <nav className="breadcrumbs" aria-label="İçerik yolu"><Link to="/">Ana Sayfa</Link><span>/</span><b>Altın Rehberi</b></nav>
      <header id="icerik"><span className="eyebrow">Altın Bilgi Merkezi</span><h1>Ons Altın Rehberi</h1>
        <p>Canlı fiyatı okumaktan model tahminlerini değerlendirmeye, gram ve ziynet altın hesabından alım satım pratiğine kadar {SEO_ARTICLES.length} rehber; beş başlık altında toplandı.</p></header>
      <div className="standalone-body">{GUIDES_BY_CATEGORY.map(([category,items])=><section key={category}>
        <h2>{category}</h2>
        <div className="hub-cards">{items.map(article=><Link className="hub-card" key={article.id} to={`/rehber/${article.id}`}>
          <small>{article.keyword}</small><b>{article.title}</b><span>{article.summary}</span></Link>)}</div>
      </section>)}</div>
    </article><SiteFooter/></main>;
}

export default GuideHub;
