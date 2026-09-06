import { useMinVisible } from '../../app/useMinVisible';
import Spinner from '../../components/Spinner';
import Collapsible from '../../components/Collapsible';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { FRAME } from '../../content/technical';
import { resolveHorizon } from '../../domain/model/horizon';
import type { Forecast } from '../../domain/model/types';
import { money } from '../../lib/format';
import type { ApiForecast } from '../../services/api/model';
import { useDashboard } from '../dashboard/DashboardContext';

/* Bağlamın `forecast`'ı domain tipiyle yayınlanır; sunucu yanıtı `...apiForecast`
   ile yayıldığı için `scenarioZones` çalışma zamanında oradadır ama tipte yok.
   Bölgeler yalnız sunucudan okunur, tarayıcıda yeniden türetilmez. */
type ForecastWithZones = Forecast & Pick<ApiForecast, 'scenarioZones'>;

function ZoneSection({ focus }: { focus?: string }) {
  const { capital, setCapital, riskPct, setRiskPct, modelStatus, hasForecast, forecast, confident, horizonDays, baseFrame } = useDashboard();
  const busy = useMinVisible(modelStatus === 'loading');
  const { index, horizon } = resolveHorizon(forecast.horizons, horizonDays);
  const hasView = confident[index] !== false;
  const zoneMap = (forecast as ForecastWithZones).scenarioZones;
  /* `undefined`: yanıt alanı taşımıyor (eski artefakt / bozuk şema) · `null`: bu vadede görüş yok. */
  const zone = zoneMap?.[String(horizon)];
  const ready = hasForecast && modelStatus !== 'fallback' && hasView && zone != null;
  /* Yalnız kullanıcı girdisine dayanan pozisyon hesabı; fiyat matematiği sunucunun `riskPerUnit`'ında. */
  const units = zone && zone.riskPerUnit > 0 ? (capital * riskPct / 100) / zone.riskPerUnit : null;
  const emptyText = !hasForecast || modelStatus === 'fallback'
    ? 'Aktif model sonucu bekleniyor. Nötr yedek veriden senaryo bölgesi üretilmez.'
    : !hasView || zone === null ? 'Bu vadede model görüş bildirmiyor'
    : 'Senaryo bölgeleri sunucudan bekleniyor';
  return (
    <Collapsible id="zones" anchor="feature-bolge" openByDefault={focus===PANEL_FEATURES.find(f=>f.anchor==="feature-bolge")?.slug} title="Model senaryosu ve risk" hint={featureBy("feature-bolge").summary} summary={null}>
    <section className="panel block terminal-zones" aria-labelledby="zone-title">
    <div className="analysis-heading"><div>
      <span className="analysis-kicker">Pozisyon hesabı</span>
      <h2 id="zone-title">Model senaryosu ve risk</h2>
    </div><span className="analysis-tag">{horizon} gün</span></div>
    {!ready && busy ? <div className="loading-row"><Spinner size="md" label="Aktif model sonucu bekleniyor…"/></div>
     : !ready || !zone ? <p className="analysis-empty">{emptyText}</p> : <>
    {modelStatus === 'loading' && <p className="model-update" role="status">Son senaryo gösteriliyor · model güncelleniyor…</p>}
    {/* Bölgeler sunucunun `base_price`'ına çapalı; hangi fiyat ve çerçeve olduğu yazılmadan seviye okunmaz. */}
    <p className="momentum-reference">Hesaplama referansı: <b>{money(forecast.price)}</b>{baseFrame && <> · {FRAME[baseFrame]}</>}</p>
    <p className="analysis-intro">{horizon} günlük model beklentisi <b>{money(zone.near)}</b> · bant genişliği <b>{money(zone.band)}</b> · ATR <b>{money(zone.atr)}</b></p>
    <div className="scenario-layout">
      <dl className="scenario-levels">
        <div><dt>Referans bölge<small>Senaryonun başlangıç aralığı</small></dt><dd>{money(zone.buy[0])} – {money(zone.buy[1])}</dd></div>
        <div><dt>Üst senaryo bölgesi<small>Model bandının üst aralığı</small></dt><dd>{money(zone.sell[0])} – {money(zone.sell[1])}</dd></div>
        <div className="risk-zone"><dt>Senaryo geçersizlik seviyesi<small>Risk bölgesinin referans sınırı</small></dt><dd>{money(zone.stop)}</dd></div>
      </dl>
      <div className="scenario-calculator">
        <h3>Örnek büyüklük hesabı</h3>
        <div className="scenario-inputs">
          <label>Portföy (USD)<input value={capital} onChange={e=>setCapital(+e.target.value)} type="number" inputMode="decimal"/></label>
          <label>Risk (%)<input value={riskPct} onChange={e=>setRiskPct(+e.target.value)} type="number" step=".1" inputMode="decimal"/></label>
        </div>
        <div className="scenario-result"><span>Risk bütçesine göre örnek azami pozisyon</span>
          {units != null
            ? <b>{units.toFixed(3)} ons <small>· {money(units * zone.entry)}</small></b>
            : <b>—<small>· ons başına risk sunucudan gelmedi</small></b>}
          <small>Ons başına planlanan risk: {money(zone.riskPerUnit)}</small></div>
      </div>
    </div>
    <p className="analysis-note">Bölgeler model beklentisi ve oynaklıktan türetilen analitik referanslardır. Alım-satım talimatı veya kişisel yatırım tavsiyesi değildir.</p>
    </>}
    </section>
    </Collapsible>
  );
}

export default ZoneSection;
