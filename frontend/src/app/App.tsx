import { Route, Routes, useParams } from 'react-router-dom';
import ErrorBoundary from '../components/ErrorBoundary';
import LegalModal from '../components/LegalModal';
import ScrollToTop from './ScrollToTop';
import { articleById } from '../content/articles';
import { featureBySlug } from '../content/panel';
import { SITE_PAGES } from '../content/pages';
import { DashboardProvider } from '../features/dashboard/DashboardContext';
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

/** Bilinmeyen rehber kimliği panele düşer: eski bağlantılar 404 yerine içerik görsün. */
const GuideRoute = () => {
  const { id } = useParams();
  const article = articleById(id!);
  return article ? <ArticlePage article={article}/> : <Dashboard/>;
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
