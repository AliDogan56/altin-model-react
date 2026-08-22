import { useMinVisible } from '../../app/useMinVisible';
import Spinner from '../../components/Spinner';
import Collapsible from '../../components/Collapsible';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { money } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

function ZoneSection({ focus }: { focus?: string }) {
  const { capital, setCapital, riskPct, setRiskPct, zones, modelStatus } = useDashboard();
  const busy = useMinVisible(modelStatus === 'loading');
  const { near, band, atr, buy, sell, stop, entry, units, horizon } = zones;
  return (
    <Collapsible id="zones" anchor="feature-bolge" openByDefault={focus===PANEL_FEATURES.find(f=>f.anchor==="feature-bolge")?.slug} title={featureBy("feature-bolge").title} hint={featureBy("feature-bolge").summary} summary={null}>
    <section className="panel block">
    <h2>İşlem bölgeleri</h2>
    {busy ? <div className="loading-row"><Spinner size="md" label="Aktif model sonucu bekleniyor…"/></div>
     : modelStatus!=='live' ? <p className="zone-basis">Aktif model sonucu bekleniyor. Nötr yedek veriden işlem bölgesi üretilmez.</p> : <>
    <p className="zone-basis">{horizon} günlük model hedefi <b>{money(near)}</b> · bant genişliği <b>{money(band)}</b> · ATR <b>{money(atr)}</b></p>
    <div className="level"><span>Kademeli alım</span><b>{money(buy[0])} – {money(buy[1])}</b></div>
    <div className="level"><span>Kâr alma</span><b>{money(sell[0])} – {money(sell[1])}</b></div>
    <div className="level danger"><span>Risk kesme</span><b>{money(stop)}</b></div>
    <label className="risk">Portföy (USD)<input value={capital} onChange={e=>setCapital(+e.target.value)} type="number"/></label>
    <label className="risk">Risk (%)<input value={riskPct} onChange={e=>setRiskPct(+e.target.value)} type="number" step=".1"/></label>
    <div className="position">Örnek azami pozisyon <b>{units.toFixed(3)} ons · {money(units*entry)}</b>
      <small>Ons başına planlanan risk: {money(entry-stop)}</small></div></>}
    </section>
    </Collapsible>
  );
}

export default ZoneSection;
