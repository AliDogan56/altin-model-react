import { Link } from 'react-router-dom';
import { GUIDES_BY_CATEGORY, SEO_ARTICLES } from '../../content/articles';

const featuredIds = ['ons-altin-tahmini', 'yapay-zeka-altin-tahmini', 'altin-fiyatini-etkileyen-faktorler'];

function SeoContent() {
  const featured = featuredIds.flatMap(id => SEO_ARTICLES.filter(article => article.id === id));
  return <section className="seo-hub editorial-resources" id="rehberler" aria-labelledby="rehberler-baslik">
    <div className="editorial-resources-head"><div><span className="eyebrow">Araştırma notları</span><h2 id="rehberler-baslik">Veriyi ve modeli anlamak</h2><p>Fiyatı okumak, modelin sınırlarını değerlendirmek ve ana parametreleri tanımak için.</p></div><Link to="/rehber">Rehber merkezini aç <span aria-hidden="true">↗</span></Link></div>
    <div className="editorial-featured">{featured.map((article, index) => <article key={article.id}>
      <small>{String(index + 1).padStart(2, '0')} / {article.category}</small>
      <h3><Link to={`/rehber/${article.id}`}>{article.title}<span aria-hidden="true">↗</span></Link></h3>
      <p>{article.summary}</p>
    </article>)}</div>
    <details className="editorial-directory">
      <summary><span>Tüm rehber başlıkları <small>{SEO_ARTICLES.length} rehber</small></span><span className="editorial-directory-toggle" aria-hidden="true">+</span></summary>
      <nav className="editorial-directory-groups" aria-label="Tüm altın rehberleri">{GUIDES_BY_CATEGORY.map(([category, articles]) => <section key={category}>
        <h3>{category}</h3>{articles.map(article => <Link key={article.id} id={article.id} to={`/rehber/${article.id}`}>{article.title}<span aria-hidden="true">↗</span></Link>)}
      </section>)}</nav>
    </details>
  </section>;
}

export default SeoContent;
