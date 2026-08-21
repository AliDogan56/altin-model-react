import { Link } from 'react-router-dom';
import { SEO_ARTICLES } from '../../content/articles';

function SeoContent() {
  return <section className="seo-hub" id="rehberler" aria-labelledby="rehberler-baslik">
    <div className="seo-intro"><span className="eyebrow">Altın Bilgi Merkezi</span><h2 id="rehberler-baslik">Ons Altın Analizi ve Tahmin Rehberleri</h2><p>Canlı fiyatı doğru okumak, modeli değerlendirmek ve altını etkileyen ekonomik göstergeleri anlamak için hazırlanan özgün rehberler.</p></div>
    <nav className="topic-pills" aria-label="Rehber konuları">{SEO_ARTICLES.map(article=><Link key={article.id} to={`/rehber/${article.id}`}>{article.keyword}</Link>)}</nav>
    <div className="seo-articles">{SEO_ARTICLES.map((article,index)=><article id={article.id} key={article.id} className="seo-article seo-card">
      <header><span>{String(index+1).padStart(2,'0')}</span><div><small>Odak konu: {article.keyword}</small><h2>{article.title}</h2><p>{article.summary}</p></div></header>
      <Link className="seo-read-more" to={`/rehber/${article.id}`} aria-label={`${article.title} rehberini oku`}>Rehberi oku <span aria-hidden="true">→</span></Link>
    </article>)}</div>
  </section>;
}

export default SeoContent;
