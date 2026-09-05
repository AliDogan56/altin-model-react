import SegmentedControl from '../../components/ui/SegmentedControl';
import InfoTooltip from '../../components/ui/InfoTooltip';
import { BAND_COVERAGE } from '../../domain/model/predict';
import { money, pct } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

/** One shared model surface; selecting a horizon updates every analysis below. */
function ForecastCards() {
  const { values, forecast, horizonDays, setHorizonDays, modelStatus, confident, hasForecast, scorecard } = useDashboard();
  const index = Math.max(0, forecast.horizons.indexOf(horizonDays));
  const available = hasForecast && modelStatus !== 'fallback';
  const sure = available && confident[index] !== false;
  const mean = forecast.mean[index];
  const metrics = scorecard?.rows.find(row => row.horizon === horizonDays);
  const direction = !available ? 'Veri bekleniyor' : !sure ? 'Görüş yok' : mean > 0 ? 'Yukarı yönlü' : mean < 0 ? 'Aşağı yönlü' : 'Yatay';
  return <section className="forecast-summary" id="feature-tahmin" aria-labelledby="forecast-title" aria-busy={modelStatus === 'loading'}>
    <div className="forecast-summary-head">
      <div><span className="section-kicker">Model görünümü</span><h2 id="forecast-title">Önümüzdeki {horizonDays} gün</h2></div>
      <SegmentedControl label="Tahmin vadesi" value={horizonDays} onChange={setHorizonDays}
        options={forecast.horizons.map(value => ({ value, label: `${value} gün` }))}/>
    </div>
    <div className="forecast-summary-values">
      <div className="forecast-direction"><span>Modelin yönü</span><strong className={sure ? mean >= 0 ? 'positive' : 'negative' : ''}>
        {sure && <span aria-hidden="true">{mean >= 0 ? '↗' : '↘'} </span>}{direction}</strong><small>{sure ? `${pct(mean)} beklenen değişim` : available ? 'Bu vadede yeterli model desteği yok' : modelStatus === 'fallback' ? 'Model servisine ulaşılamıyor' : 'Model sonucu hazırlanıyor'}</small></div>
      <div><span>Model beklentisi</span><strong className="forecast-target">{sure ? money(values.price * (1 + mean)) : '—'}</strong><small>{horizonDays} takvim günü sonrası</small></div>
      <div><span>Olasılık bandı <InfoTooltip label="Olasılık bandı">%{BAND_COVERAGE} nominal olasılık bandıdır; yönün doğru çıkma olasılığı veya kişisel güven skoru değildir. Gerçekleşen fiyat bu aralığın dışında kalabilir.</InfoTooltip></span><strong className="forecast-band">{sure ? `${money(values.price * (1 + mean - forecast.err[index]))} – ${money(values.price * (1 + mean + forecast.err[index]))}` : '—'}</strong><small>%{BAND_COVERAGE} nominal kapsam</small></div>
      <div><span>Geçmiş yön isabeti <InfoTooltip label="Geçmiş yön isabeti">Eğitim dışında kalan günlerde ölçülen yön doğruluğu. Bugünkü tahminin güven yüzdesi değildir.</InfoTooltip></span><strong>{metrics ? `%${(metrics.direction * 100).toFixed(1)}` : '—'}</strong><small>{metrics ? `${metrics.oofRows} test günü · ${horizonDays} günlük model` : 'Model karnesi bekleniyor'}</small></div>
    </div>
    {modelStatus === 'loading' && <p className="model-update" role="status">{hasForecast ? 'Son model sonucu gösteriliyor · güncelleniyor…' : 'Model hesaplanıyor…'}</p>}
  </section>;
}

export default ForecastCards;
