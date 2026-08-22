import { Link } from 'react-router-dom';
import SiteFooter from '../components/SiteFooter';
import SiteNav from '../components/SiteNav';
import { SITE_PAGES } from '../content/pages';
import type { SitePage } from '../content/types';
import { useDocumentMeta } from '../app/useDocumentMeta';

/** Kurumsal sayfalar tek şablondan basılır; rehber makaleleriyle aynı okuma düzeni. */
function SitePageView({ page }: { page: SitePage }) {
  // useDocumentMeta site adını kendisi ekler; burada eklemek başlığı iki kez markalıyordu.
  useDocumentMeta(page.seoTitle, page.summary, `/${page.slug}`);
  return (
    <main className="app article-page">
      <SiteNav/>
      <article className="standalone-article">
        <nav className="breadcrumbs" aria-label="İçerik yolu">
          <Link to="/">Ana Sayfa</Link><span>/</span><b>{page.title}</b>
        </nav>
        <header id="icerik"><h1>{page.title}</h1><p>{page.summary}</p></header>
        <div className="standalone-body">
          {page.sections.map(section => (
            <section key={section.heading}>
              <h2>{section.heading}</h2>
              {section.paragraphs.map((paragraph, i) => <p key={i}>{paragraph}</p>)}
            </section>
          ))}
          <p className="article-updated"><small>Son güncelleme: {page.updated}</small></p>
          <nav className="related-guides" aria-label="Diğer sayfalar">
            <h2>Diğer sayfalar</h2>
            <div>{SITE_PAGES.filter(other => other.slug !== page.slug).map(other =>
              <Link to={`/${other.slug}`} key={other.slug}>
                <b>{other.title}</b><span aria-hidden="true">→</span></Link>)}
            </div>
          </nav>
        </div>
      </article>
      <SiteFooter/>
    </main>
  );
}

export default SitePageView;
