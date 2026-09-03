import { useEffect, useState } from 'react';
import { Route, Routes, useParams } from 'react-router-dom';
import ErrorBoundary from '../components/ErrorBoundary';
import LegalModal from '../components/LegalModal';
import ScrollToTop from './ScrollToTop';
import { articleFromPage, loadArticle } from '../content/articles';
import { featureBySlug } from '../content/panel';
import { SITE_PAGES } from '../content/pages';
import { DashboardProvider } from '../features/dashboard/DashboardContext';
import Spinner from '../components/Spinner';
import SiteNav from '../components/SiteNav';
import type { SeoArticle } from '../content/types';
import ArticlePage from '../pages/ArticlePage';
import DashboardPage from '../pages/DashboardPage';
import GuideHubPage from '../pages/GuideHubPage';
import PanelHubPage from '../pages/PanelHubPage';
import SitePageView from '../pages/SitePageView';

/** Panel durumu yalnız panel sayfalarında kurulur; rehber sayfaları soket açmaz. */
const Dashboard = ({ focus }: { focus?: string }) => (
  <ErrorBoundary title="Panel yüklenemedi">
    <DashboardProvider><DashboardPage focus={focus}/></DashboardProvider>
  </ErrorBoundary>
);

const PanelFeatureRoute = () => {
  const { slug } = useParams();
  return <Dashboard focus={featureBySlug(slug!) ? slug : undefined}/>;
};

/**
 * Rehber rotası. Makale gövdesi ana pakette değil (37 makale = 84 KB gzip);
 * iki yoldan gelir:
 *
 *   1. **Organik iniş** — ön render edilen sayfa gövdeyi gömülü taşır ve
 *      `useState` başlangıç değeri olarak **eşzamanlı** okunur. Hidrasyonda
 *      içeriğin bir an kaybolması böyle önlenir; asıl SEO yolu budur.
 *   2. **Uygulama içi gezinme** — tam veri bir kez tembel yüklenir.
 *
 * Bilinmeyen rehber kimliği panele düşer: eski bağlantılar 404 yerine içerik görsün.
 */
const GuideRoute = () => {
  const { id } = useParams();
  const [article, setArticle] = useState<SeoArticle | null>(() => articleFromPage(id!));
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    if (article?.id === id) return;
    let cancelled = false;
    setMissing(false);
    loadArticle(id!).then(found => {
      if (cancelled) return;
      setArticle(found);
      setMissing(!found);
    });
    return () => { cancelled = true; };
  }, [id, article]);

  if (article && article.id === id) return <ArticlePage article={article}/>;
  if (missing) return <Dashboard/>;
  return <main className="app article-page"><SiteNav current={id}/>
    <div className="article-loading"><Spinner size="lg" label="Rehber yükleniyor…"/></div>
  </main>;
};

function App() {
  return (
    <>
      <ScrollToTop/>
      <ErrorBoundary>
      <Routes>
        {SITE_PAGES.map(page =>
          <Route key={page.slug} path={`/${page.slug}`} element={<SitePageView page={page}/>}/>)}
        <Route path="/rehber" element={<GuideHubPage/>}/>
        <Route path="/rehber/:id" element={<GuideRoute/>}/>
        <Route path="/panel" element={<PanelHubPage/>}/>
        <Route path="/panel/:slug" element={<PanelFeatureRoute/>}/>
        <Route path="*" element={<Dashboard/>}/>
      </Routes>
      </ErrorBoundary>
      <LegalModal/>
    </>
  );
}

export default App;
