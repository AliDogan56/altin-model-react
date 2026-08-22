import SiteFooter from '../components/SiteFooter';
import ErrorBoundary from '../components/ErrorBoundary';
import { useMinVisible } from '../app/useMinVisible';
import Spinner from '../components/Spinner';
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
  const { ziynet, scorecard, tech, pivotLadder, modelStatus } = useDashboard();
  const ziynetBusy = useMinVisible(!ZIYNET.some(([code]) => ziynet[code]));
  const detailsBusy = useMinVisible(!scorecard && !tech && !pivotLadder);
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
          {!ziynetBusy
            ? <ErrorBoundary title="Ziynet fiyatları yüklenemedi"><ZiynetSection/></ErrorBoundary>
            /* Kotasyon gelene kadar bölüm hiç basılmıyordu; ekranda sebepsiz bir
               boşluk kalıyor ve kullanıcı bir şeyin yüklendiğini göremiyordu. */
            : <section className="panel block gram-block" aria-busy="true">
                <h2>{'Canlı Ziynet Altın Fiyatları'}</h2>
                <div className="loading-row"><Spinner size="lg" label="Canlı kotasyona bağlanılıyor…"/></div>
              </section>}
          <ErrorBoundary title="Grafik yüklenemedi"><ChartSection/></ErrorBoundary>
          <div className="section-label"><span>Ayrıntılar</span><small>Başlığa dokunarak açın</small></div>
          {/* Servis çevrimdışıyken bu bölümler hiç gelmez; sonsuza kadar dönen
              bir spinner göstermek yanıltıcı olurdu, durumu yazıyoruz. */}
          {detailsBusy && (modelStatus==='fallback'
            ? <p className="loading-row">Model servisi çevrimdışı; ayrıntı bölümleri bu oturumda gösterilemiyor.</p>
            : <div className="loading-row" aria-busy="true"><Spinner size="md" label="Ayrıntı bölümleri hazırlanıyor…"/></div>)}
          {!detailsBusy&&scorecard&&<ErrorBoundary title="İsabet karnesi yüklenemedi"><ScorecardSection focus={focus}/></ErrorBoundary>}
          {!detailsBusy&&tech&&<ErrorBoundary title="Teknik göstergeler yüklenemedi"><IndicatorsSection focus={focus}/></ErrorBoundary>}
          {!detailsBusy&&pivotLadder&&<ErrorBoundary title="Pivot seviyeleri yüklenemedi"><PivotSection focus={focus}/></ErrorBoundary>}
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
