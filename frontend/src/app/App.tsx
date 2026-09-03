import { lazy, Suspense, useEffect, useState } from 'react';
import { Route, Routes, useLocation, useParams } from 'react-router-dom';
import ErrorBoundary from '../components/ErrorBoundary';
import LegalModal from '../components/LegalModal';
import ScrollToTop from './ScrollToTop';
import { prerenderConsumed, prerenderFor } from './prerender';
import { articleFromPage, loadArticle } from '../content/articles';
import { featureBySlug } from '../content/panel';
import { SITE_PAGES } from '../content/pages';
import Spinner from '../components/Spinner';
import SiteNav from '../components/SiteNav';
import type { SeoArticle } from '../content/types';

/**
 * Rota bazlı kod bölme. Her sayfa türü kendi parçasında: rehber okuyucusu
 * panelin grafik ve socket.io kodunu, panel kullanıcısı makale sayfasını
 * indirmez. Ön render edilen sayfalar ilgili parçayı `modulepreload` ile
 * baştan ister (scripts/generate-seo-pages.mjs), yani ek gidiş-dönüş yok.
 */
const DashboardRoute = lazy(() => import('../pages/DashboardRoute'));
const ArticlePage = lazy(() => import('../pages/ArticlePage'));
const GuideHubPage = lazy(() => import('../pages/GuideHubPage'));
const PanelHubPage = lazy(() => import('../pages/PanelHubPage'));
const SitePageView = lazy(() => import('../pages/SitePageView'));

const LoadingPage = ({ label }: { label: string }) =>
  <main className="app article-page"><div className="article-loading"><Spinner size="lg" label={label}/></div></main>;

/** Parça gelene kadar: organik inişte ön render edilmiş metnin kendisi, aksi hâlde spinner. */
const RouteFallback = () => {
  const { pathname } = useLocation();
  const html = prerenderFor(pathname);
  if (html) return <div dangerouslySetInnerHTML={{ __html: html }}/>;
  return <LoadingPage label="Sayfa yükleniyor…"/>;
};

/** Suspense sınırı çözüldüğünde render olur: ön render yedeği bir daha kullanılmaz. */
const PrerenderDone = () => { useEffect(prerenderConsumed, []); return null; };

const PanelFeatureRoute = () => {
  const { slug } = useParams();
  return <DashboardRoute focus={featureBySlug(slug!) ? slug : undefined}/>;
};

/**
 * Rehber rotası. Makale gövdesi ana pakette değil (37 makale = 84 KB gzip);
 * iki yoldan gelir:
 *
 *   1. **Organik iniş** — ön render edilen sayfa gövdeyi gömülü taşır ve
 *      `useState` başlangıç değeri olarak **eşzamanlı** okunur.
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
  if (missing) return <DashboardRoute/>;
  return <><SiteNav current={id}/><LoadingPage label="Rehber yükleniyor…"/></>;
};

function App() {
  return (
    <>
      <ScrollToTop/>
      <ErrorBoundary>
      <Suspense fallback={<RouteFallback/>}>
        <Routes>
          {SITE_PAGES.map(page =>
            <Route key={page.slug} path={`/${page.slug}`} element={<SitePageView page={page}/>}/>)}
          <Route path="/rehber" element={<GuideHubPage/>}/>
          <Route path="/rehber/:id" element={<GuideRoute/>}/>
          <Route path="/panel" element={<PanelHubPage/>}/>
          <Route path="/panel/:slug" element={<PanelFeatureRoute/>}/>
          <Route path="*" element={<DashboardRoute/>}/>
        </Routes>
        <PrerenderDone/>
      </Suspense>
      </ErrorBoundary>
      <LegalModal/>
    </>
  );
}

export default App;
