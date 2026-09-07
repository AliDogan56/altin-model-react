import { useMinVisible } from '../../app/useMinVisible';
import Spinner from '../../components/Spinner';
import Collapsible from '../../components/Collapsible';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { money } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

function ZoneSection({ focus }: { focus?: string }) {
  const { capital, setCapital, riskPct, setRiskPct, zones, modelStatus, hasForecast, forecast, confident } = useDashboard();
  const busy = useMinVisible(modelStatus === 'loading');
  const { near, band, atr, buy, sell, stop, entry, units, horizon } = zones;
  const hasView = confident[Math.max(0, forecast.horizons.indexOf(horizon))] !== false;
  const ready = hasForecast && modelStatus !== 'fallback' && hasView;
  return (
    <Collapsible id="zones" anchor="feature-bolge" openByDefault={focus===PANEL_FEATURES.find(f=>f.anchor==="feature-bolge")?.slug} title="Model senaryosu ve risk" hint={featureBy("feature-bolge").summary} summary={null}>
    <section className="panel block terminal-zones" aria-labelledby="zone-title">
    <div className="analysis-heading"><div>
      <span className="analysis-kicker">Pozisyon hesabı</span>
      <h2 id="zone-title">Model senaryosu ve risk</h2>
    </div><span className="analysis-tag">{horizon} gün</span></div>
    {!ready && busy ? <div className="loading-row"><Spinner size="md" label="Aktif model sonucu bekleniyor…"/></div>
     : !ready ? <p className="analysis-empty">{hasForecast && !hasView ? 'Model bu vadede görüş bildirmiyor; senaryo seviyeleri gösterilmiyor.' : 'Aktif model sonucu bekleniyor. Nötr yedek veriden senaryo bölgesi üretilmez.'}</p> : <>
    {modelStatus === 'loading' && <p className="model-update" role="status">Son senaryo gösteriliyor · model güncelleniyor…</p>}
    <p className="analysis-intro">{horizon} günlük model beklentisi <b>{money(near)}</b> · bant genişliği <b>{money(band)}</b> · ATR <b>{money(atr)}</b></p>
    <div className="scenario-layout">
      <dl className="scenario-levels">
        <div><dt>Referans bölge<small>Senaryonun başlangıç aralığı</small></dt><dd>{money(buy[0])} – {money(buy[1])}</dd></div>
        <div><dt>Üst senaryo bölgesi<small>Model bandının üst aralığı</small></dt><dd>{money(sell[0])} – {money(sell[1])}</dd></div>
        <div className="risk-zone"><dt>Senaryo geçersizlik seviyesi<small>Risk bölgesinin referans sınırı</small></dt><dd>{money(stop)}</dd></div>
      </dl>
      <div className="scenario-calculator">
        <h3>Örnek büyüklük hesabı</h3>
        <div className="scenario-inputs">
          <label>Portföy (USD)<input value={capital} onChange={e=>setCapital(+e.target.value)} type="number" inputMode="decimal"/></label>
          <label>Risk (%)<input value={riskPct} onChange={e=>setRiskPct(+e.target.value)} type="number" step=".1" inputMode="decimal"/></label>
        </div>
        <div className="scenario-result"><span>Risk bütçesine göre örnek azami pozisyon</span><b>{units.toFixed(3)} ons <small>· {money(units*entry)}</small></b>
          <small>Ons başına planlanan risk: {money(entry-stop)}</small></div>
      </div>
    </div>
    <p className="analysis-note">Bölgeler model beklentisi ve oynaklıktan türetilen analitik referanslardır. Alım-satım talimatı veya kişisel yatırım tavsiyesi değildir.</p>
    </>}
    </section>
    </Collapsible>
  );
}

export default ZoneSection;
