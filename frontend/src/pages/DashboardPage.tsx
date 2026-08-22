import SiteFooter from '../components/SiteFooter';
import ErrorBoundary from '../components/ErrorBoundary';
import SiteNav from '../components/SiteNav';
import { featureBySlug } from '../content/panel';
import { PAGE_META } from '../content/site';
import { useDocumentMeta } from '../app/useDocumentMeta';
import BulletinSection from '../features/bulletin/BulletinSection';
import ChartSection from '../features/chart/ChartSection';
import { useDashboard } from '../features/dashboard/DashboardContext';
import PanelHeader from '../features/dashboard/PanelHeader';
import { useFeatureFocus } from '../features/dashboard/useFeatureFocus';
import ForecastCards from '../features/forecast/ForecastCards';
import SeoContent from '../features/guides/SeoContent';
import ImpactSection from '../features/impact/ImpactSection';
import IndicatorsSection from '../features/indicators/IndicatorsSection';
import LoanSection from '../features/loan/LoanSection';
import PivotSection from '../features/pivots/PivotSection';
import ScorecardSection from '../features/scorecard/ScorecardSection';
import ZiynetSection from '../features/ziynet/ZiynetSection';
import ZoneSection from '../features/zones/ZoneSection';
import { ZIYNET } from '../services/realtime/harem';

/** Panel yerleşimi: ana özellikler üstte açık, yan özellikler akordiyonda.
 *  Bölümlerin kendi verisi context'ten gelir; buradan prop geçilmez. */
function DashboardPage({ focus }: { focus?: string }) {
  const { ziynet, scorecard, tech, pivotLadder } = useDashboard();
  const feature = focus ? featureBySlug(focus) ?? null : null;
  useDocumentMeta(PAGE_META.home.title, PAGE_META.home.description, PAGE_META.home.path, !feature);
  useFeatureFocus(feature);

  return (
    <main className="app">
      <SiteNav/>
      <PanelHeader/>
      <div className="layout">
        <section className="content">
          <div className="section-label"><span>Ana görünüm</span></div>
          {/* Her bölüm kendi sınırında: biri çökerse diğerleri okunur kalır. */}
          <ErrorBoundary title="Tahmin kartları yüklenemedi"><ForecastCards/></ErrorBoundary>
          {ZIYNET.some(([code])=>ziynet[code])&&
            <ErrorBoundary title="Ziynet fiyatları yüklenemedi"><ZiynetSection/></ErrorBoundary>}
          <ErrorBoundary title="Grafik yüklenemedi"><ChartSection/></ErrorBoundary>
          <div className="section-label"><span>Ayrıntılar</span><small>Başlığa dokunarak açın</small></div>
          {scorecard&&<ErrorBoundary title="İsabet karnesi yüklenemedi"><ScorecardSection focus={focus}/></ErrorBoundary>}
          {tech&&<ErrorBoundary title="Teknik göstergeler yüklenemedi"><IndicatorsSection focus={focus}/></ErrorBoundary>}
          {pivotLadder&&<ErrorBoundary title="Pivot seviyeleri yüklenemedi"><PivotSection focus={focus}/></ErrorBoundary>}
          <ErrorBoundary title="Parametre katkısı yüklenemedi"><ImpactSection focus={focus}/></ErrorBoundary>
          <ErrorBoundary title="TL getirisi yüklenemedi"><LoanSection focus={focus}/></ErrorBoundary>
          <ErrorBoundary title="Bülten yüklenemedi"><BulletinSection focus={focus}/></ErrorBoundary>
          <ErrorBoundary title="İşlem bölgeleri yüklenemedi"><ZoneSection focus={focus}/></ErrorBoundary>
          <SeoContent/>
          <SiteFooter/>
        </section>
      </div>
    </main>
  );
}

export default DashboardPage;
