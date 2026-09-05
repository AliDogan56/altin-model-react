import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import SiteFooter from '../components/SiteFooter';
import ErrorBoundary from '../components/ErrorBoundary';
import SiteNav from '../components/SiteNav';
import { AnalysisPresentation } from '../components/Collapsible';
import SegmentedControl from '../components/ui/SegmentedControl';
import DataTimestamp from '../components/ui/DataTimestamp';
import { featureBySlug } from '../content/panel';
import { openLegal, PAGE_META } from '../content/site';
import { useDocumentMeta } from '../app/useDocumentMeta';
import BulletinSection from '../features/bulletin/BulletinSection';
import ChartSection from '../features/chart/ChartSection';
import { useDashboard } from '../features/dashboard/DashboardContext';
import PanelHeader from '../features/dashboard/PanelHeader';
import PanelIntro from '../features/dashboard/PanelIntro';
import OverviewInsights from '../features/dashboard/OverviewInsights';
import { useFeatureFocus } from '../features/dashboard/useFeatureFocus';
import ForecastCards from '../features/forecast/ForecastCards';
import SeoContent from '../features/guides/SeoContent';
import ImpactSection from '../features/impact/ImpactSection';
import MomentumSection, { MomentumSummary } from '../features/momentum/MomentumSection';
import IndicatorsSection from '../features/indicators/IndicatorsSection';
import LoanSection from '../features/loan/LoanSection';
import PivotSection from '../features/pivots/PivotSection';
import PriceLadder from '../features/pivots/PriceLadder';
import ScorecardSection from '../features/scorecard/ScorecardSection';
import TrendSection from '../features/trend/TrendSection';
import ZiynetSection from '../features/ziynet/ZiynetSection';
import ZoneSection from '../features/zones/ZoneSection';
import { money } from '../lib/format';

const VIEWS = [
  ['overview', 'Genel bakış', '01'], ['technical', 'Teknik analiz', '02'],
  ['model', 'Model', '03'], ['markets', 'Piyasalar', '04'], ['scenarios', 'Senaryolar', '05'],
] as const;
type View = typeof VIEWS[number][0];
const ANCHOR_VIEW: Record<string, View> = {
  'feature-tahmin': 'overview', 'feature-grafik': 'overview',
  'feature-trend': 'technical', 'feature-pivot': 'technical', 'feature-momentum': 'technical', 'feature-teknik': 'technical',
  'feature-karne': 'model', 'feature-katki': 'model',
  'feature-ziynet': 'markets', 'feature-bulten': 'markets', 'feature-tl': 'scenarios', 'feature-bolge': 'scenarios',
};
const viewOf = (value: string | null): View | null => VIEWS.some(([key]) => key === value) ? value as View : null;
const Boundary = ({ children }: { children: ReactNode }) => <ErrorBoundary title="Bu analiz yüklenemedi">{children}</ErrorBoundary>;

function DashboardPage({ focus }: { focus?: string }) {
  const { scorecard, tech, pivotLadder, modelStatus, hasForecast, featuresDate, pivotPeriod, pivotMethod, horizonDays, setHorizonDays, forecast } = useDashboard();
  const feature = focus ? featureBySlug(focus) ?? null : null;
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const anchor = location.hash.slice(1);
  const active = viewOf(params.get('view')) ?? ANCHOR_VIEW[feature?.anchor ?? anchor] ?? 'overview';
  const [visited, setVisited] = useState<Set<View>>(() => new Set([active]));
  const tabs = useRef<HTMLDivElement>(null);
  useEffect(() => { setVisited(old => old.has(active) ? old : new Set([...old, active])); }, [active]);
  useDocumentMeta(PAGE_META.home.title, PAGE_META.home.description, PAGE_META.home.path, !feature);
  useFeatureFocus(feature);
  useEffect(() => {
    if (!anchor || feature) return;
    const frame = requestAnimationFrame(() => document.getElementById(anchor === 'tahmin' ? 'feature-tahmin' : anchor)?.scrollIntoView({ block: 'start' }));
    return () => cancelAnimationFrame(frame);
  }, [anchor, active, feature]);
  const select = (next: View) => setParams({ view: next }, { preventScrollReset: true });
  const panel = (view: View, children: ReactNode) => <div key={view} id={`workspace-${view}`} role="tabpanel" aria-labelledby={`tab-${view}`} hidden={active !== view} tabIndex={0} className="workspace-panel">
    {(visited.has(view) || active === view) && children}
  </div>;
  const nearDown = pivotLadder?.items.find(item => item.name === pivotLadder.nearestDown);
  const nearUp = pivotLadder?.items.find(item => item.name === pivotLadder.nearestUp);
  const pivot = pivotLadder?.items.find(item => item.name === 'P');
  const modelReady = hasForecast && modelStatus !== 'fallback';

  return <main className="app terminal-app">
    <SiteNav/>
    <PanelHeader demoted={!!feature?.sections?.length}/>
    <div id="icerik" className="workspace-tabs" role="tablist" aria-label="Analiz alanları" tabIndex={-1} ref={tabs}>
      {VIEWS.map(([key, label, number], index) => <button type="button" key={key} role="tab" id={`tab-${key}`}
        aria-controls={`workspace-${key}`} aria-selected={active === key} tabIndex={active === key ? 0 : -1}
        onClick={() => select(key)} onKeyDown={event => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? VIEWS.length - 1
            : (index + (event.key === 'ArrowRight' ? 1 : -1) + VIEWS.length) % VIEWS.length;
          select(VIEWS[next][0]); tabs.current?.querySelectorAll('button')[next]?.focus();
        }}><span aria-hidden="true">{number}</span>{label}</button>)}
    </div>
    <AnalysisPresentation.Provider value="section">
      {panel('overview', <>
        <div className="overview-workspace">
          <div className="model-surface">
            <Boundary><ForecastCards/></Boundary>
            <Boundary><ChartSection/></Boundary>
          </div>
          <aside className="overview-rail" aria-label="Seviyeler ve momentum">
            <section className="rail-section" aria-labelledby="rail-levels-title">
              <div className="rail-heading"><div><span className="section-kicker">Fiyatın konumu</span><h2 id="rail-levels-title">Destek & direnç</h2></div><button className="icon-action" type="button" onClick={() => select('technical')} aria-label="Tüm teknik analizleri aç">↗</button></div>
              <dl className="nearest-levels"><div><dt>↓ İlk destek</dt><dd>{nearDown ? money(nearDown.value) : '—'}</dd></div><div><dt>↑ İlk direnç</dt><dd>{nearUp ? money(nearUp.value) : '—'}</dd></div></dl>
              <Boundary><PriceLadder ladder={pivotLadder}/></Boundary>
              <p className="rail-note">{pivot && pivotLadder ? `Fiyat pivotun ${pivotLadder.price >= pivot.value ? 'üzerinde' : 'altında'}.` : 'Seviyeler hazırlanıyor.'} {pivotPeriod === 'weekly' ? 'Haftalık' : 'Aylık'} · {pivotMethod === 'fib' ? 'Fibonacci' : 'Klasik'}</p>
            </section>
            <Boundary><MomentumSummary onOpen={() => select('technical')}/></Boundary>
          </aside>
        </div>
        <Boundary><OverviewInsights onModel={() => select('model')}/></Boundary>
      </>)}
      {panel('technical', <div className="analysis-stack">
        <div className="workspace-heading"><div><span className="section-kicker">Piyasanın yapısı</span><h2>Trend, seviyeler ve momentum</h2></div><DataTimestamp time={featuresDate} staleAfterMs={7 * 86400000}/></div>
        <Boundary><TrendSection/></Boundary>
        <div className="analysis-columns"><Boundary><PivotSection focus={focus}/></Boundary><Boundary><MomentumSection focus={focus}/></Boundary></div>
        {tech ? <Boundary><IndicatorsSection focus={focus}/></Boundary> : <p className="data-empty">Teknik göstergeler için fiyat geçmişi bekleniyor.</p>}
      </div>)}
      {panel('model', <div className="analysis-stack">
        <div className="workspace-heading"><div><span className="section-kicker">Model araştırması</span><h2>Tahminin dayanakları ve performansı</h2></div><SegmentedControl label="Model analizi vadesi" value={horizonDays} onChange={setHorizonDays} options={forecast.horizons.map(value => ({ value, label: `${value} gün` }))}/></div>
        <Boundary><ImpactSection focus={focus}/></Boundary>
        {scorecard ? <Boundary><ScorecardSection focus={focus}/></Boundary> : <p className="data-empty">Model karnesi {modelStatus === 'fallback' ? 'servise ulaşılamadığı için gösterilemiyor.' : 'bekleniyor.'}</p>}
      </div>)}
      {panel('markets', <div className="analysis-stack">
        <div className="workspace-heading"><div><span className="section-kicker">Piyasa takibi</span><h2>Ziynet fiyatları ve makro gelişmeler</h2></div></div>
        <Boundary><ZiynetSection/></Boundary><Boundary><BulletinSection focus={focus}/></Boundary>
      </div>)}
      {panel('scenarios', <div className="analysis-stack">
        <div className="workspace-heading"><div><span className="section-kicker">Varsayımları incele</span><h2>Getiri ve risk senaryoları</h2><p>Seçili model vadesini, kur ve finansman varsayımlarıyla birlikte değerlendirin.</p></div><SegmentedControl label="Senaryo vadesi" value={horizonDays} onChange={setHorizonDays} options={forecast.horizons.map(value => ({ value, label: `${value} gün` }))}/></div>
        <Boundary><LoanSection focus={focus}/></Boundary><Boundary><ZoneSection focus={focus}/></Boundary>
      </div>)}
    </AnalysisPresentation.Provider>
    <div className="terminal-status"><span><i className={modelReady ? 'ready' : ''} aria-hidden="true"/>{modelReady ? 'Model bağlantısı açık' : modelStatus === 'fallback' ? 'Model servisi çevrimdışı' : 'Model bekleniyor'}</span><span>XAU/USD · 7 / 14 / 30 günlük model</span><button className="link-btn" type="button" onClick={openLegal}>İstatistiksel senaryo · yatırım tavsiyesi değildir</button></div>
    {feature?.sections?.length ? <PanelIntro feature={feature}/> : null}
    <SeoContent/>
    <SiteFooter/>
  </main>;
}

export default DashboardPage;
