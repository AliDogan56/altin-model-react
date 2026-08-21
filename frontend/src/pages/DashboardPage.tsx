import SiteFooter from '../components/SiteFooter';
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
import ParameterPanel from '../features/parameters/ParameterPanel';
import PivotSection from '../features/pivots/PivotSection';
import ScorecardSection from '../features/scorecard/ScorecardSection';
import ZiynetSection from '../features/ziynet/ZiynetSection';
import ZoneSection from '../features/zones/ZoneSection';
import { ZIYNET } from '../services/realtime/harem';

/** Panel yerleşimi: ana özellikler üstte açık, yan özellikler akordiyonda.
 *  Bölümlerin kendi verisi context'ten gelir; buradan prop geçilmez. */
function DashboardPage({ focus }: { focus?: string }) {
  const { wideChart, setWideChart, ziynet, scorecard, tech, pivotLadder } = useDashboard();
  const feature = focus ? featureBySlug(focus) ?? null : null;
  useDocumentMeta(PAGE_META.home.title, PAGE_META.home.description, PAGE_META.home.path, !feature);
  useFeatureFocus(feature);

  return (
    <main className="app">
      <SiteNav/>
      <PanelHeader/>
      <div className="parameter-toggle-bar">
        <button onClick={()=>setWideChart(v=>!v)} aria-expanded={!wideChart}>
          <span>⚙</span>{wideChart?'Parametreleri göster':'Parametreleri gizle'}
        </button>
      </div>
      <div className={`layout ${wideChart?'wide-chart':''}`}>
        <ParameterPanel/>
        <section className="content">
          <div className="section-label"><span>Ana görünüm</span></div>
          <ForecastCards/>
          <ChartSection/>
          {ZIYNET.some(([code])=>ziynet[code])&&<ZiynetSection/>}
          {scorecard&&<ScorecardSection/>}
          <div className="section-label"><span>Ayrıntılar</span><small>Başlığa dokunarak açın</small></div>
          {tech&&<IndicatorsSection focus={focus}/>}
          {pivotLadder&&<PivotSection focus={focus}/>}
          <ImpactSection focus={focus}/>
          <LoanSection focus={focus}/>
          <BulletinSection focus={focus}/>
          <ZoneSection focus={focus}/>
          <SeoContent/>
          <SiteFooter/>
        </section>
      </div>
    </main>
  );
}

export default DashboardPage;
