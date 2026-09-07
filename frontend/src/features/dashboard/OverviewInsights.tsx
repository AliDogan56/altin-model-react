import { useDashboard } from './DashboardContext';
import { money } from '../../lib/format';

export default function OverviewInsights({ onModel }: { onModel: () => void }) {
  const { impacts, modelStatus, confident, forecast } = useDashboard();
  const hasView = confident[Math.max(0, forecast.horizons.indexOf(impacts.horizon))] !== false;
  const drivers = [...impacts.up, ...impacts.down].sort((a, b) => Math.abs(b.usd) - Math.abs(a.usd)).slice(0, 3);
  return <section className="overview-insights" aria-labelledby="overview-insight-title">
    <div className="overview-insight-title"><span className="section-kicker">Görüşün arkasında</span><h2 id="overview-insight-title">Modeli ne etkiliyor?</h2><button type="button" className="text-action" onClick={onModel}>Modeli incele <span aria-hidden="true">↗</span></button></div>
    <div className="overview-drivers">{impacts.live && hasView && modelStatus !== 'fallback' && drivers.length ? drivers.map(driver => <div key={driver.key}>
      <span>{driver.label}</span><b className={driver.usd >= 0 ? 'positive' : 'negative'}>{driver.usd >= 0 ? '+' : '−'}{money(Math.abs(driver.usd))}</b>
      <div className="mini-contribution" aria-hidden="true"><i className={driver.usd >= 0 ? 'up' : 'down'} style={{ width: `${Math.max(2, driver.share * 50)}%` }}/></div>
    </div>) : <p className="data-empty">{impacts.live && !hasView ? 'Model seçili vadede görüş bildirmiyor; katkı özeti gösterilmiyor.' : 'Parametre katkıları için model sonucu bekleniyor.'}</p>}</div>
    <p className="analysis-footnote">Seçili vadede, her girdinin kendi ortalamasına göre tekil model etkisi. Katkılar nedensellik göstermez.</p>
  </section>;
}
