import { Link } from 'react-router-dom';
import SiteFooter from '../components/SiteFooter';
import SiteNav from '../components/SiteNav';
import { PANEL_FEATURES } from '../content/panel';
import { PAGE_META } from '../content/site';
import { useDocumentMeta } from '../app/useDocumentMeta';

/** /panel dizini: her özelliğin kendi SEO sayfasına giden gerçek bir sayfa.
 *  Sitemap ve canonical burayı gösterdiği için doğrudan 200 dönmesi gerekir. */
function PanelHubPage() {
  useDocumentMeta(PAGE_META.panel.title, PAGE_META.panel.description, PAGE_META.panel.path);
  return (
    <main className="app article-page">
      <SiteNav/>
      <article className="standalone-article">
        <nav className="breadcrumbs" aria-label="İçerik yolu">
          <Link to="/">Ana Sayfa</Link><span>/</span><b>Panel özellikleri</b>
        </nav>
        <header id="icerik">
          <span className="eyebrow">Canlı panel</span>
          <h1>Canlı altın panelindeki analiz özellikleri</h1>
          <p>Panelin {PANEL_FEATURES.length} bölümü; her biri kendi sayfasından açılır ve panelde ilgili karta odaklanır.</p>
        </header>
        <div className="standalone-body">
          <div className="hub-cards">
            {PANEL_FEATURES.map(feature =>
              <Link className="hub-card" key={feature.slug} to={`/panel/${feature.slug}`}>
                <small>Canlı panel</small><b>{feature.title}</b><span>{feature.summary}</span>
              </Link>)}
          </div>
        </div>
      </article>
      <SiteFooter/>
    </main>
  );
}

export default PanelHubPage;
