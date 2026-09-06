import SegmentedControl from '../../components/ui/SegmentedControl';
import InfoTooltip from '../../components/ui/InfoTooltip';
import { FRAME } from '../../content/technical';
import { resolveHorizon } from '../../domain/model/horizon';
import { intervalLabel } from '../../domain/model/predict';
import { money, pct } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

/** One shared model surface; selecting a horizon updates every analysis below. */
function ForecastCards() {
  const { forecast, horizonDays, setHorizonDays, modelStatus, confident, hasForecast, scorecard, clipped, baseFrame } = useDashboard();
  /* Listede olmayan ufukta sessizce ilk ufka düşmek yerine en yakını seçilir. */
  const { index } = resolveHorizon(forecast.horizons, horizonDays);
  const available = hasForecast && modelStatus !== 'fallback';
  const sure = available && confident[index] !== false;
  const mean = forecast.mean[index];
  const bandLabel = intervalLabel(forecast, index);
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
      <div><span>Model beklentisi</span><strong className="forecast-target">{sure ? money(forecast.price * (1 + mean)) : '—'}</strong><small>{horizonDays} takvim günü sonrası</small></div>
      <div><span>Olasılık bandı <InfoTooltip label="Olasılık bandı">{bandLabel}. Nominal kapsam, geçmiş artıkların hedef yüzdeliğidir; bugünkü volatiliteyle ölçeklenmiş bandın gerçekleşen kapsamı henüz doğrulanmamıştır. Yön doğruluğu veya güven skoru değildir.</InfoTooltip></span><strong className="forecast-band">{sure ? `${money(forecast.price * (1 + mean - forecast.err[index]))} – ${money(forecast.price * (1 + mean + forecast.err[index]))}` : '—'}</strong><small>{bandLabel} · canlı kapsam ölçülmedi</small></div>
      <div><span>Geçmiş yön isabeti <InfoTooltip label="Geçmiş yön isabeti">Eğitim dışında kalan günlerde ölçülen yön doğruluğu. Görüş yok günleri yeni ölçümde yön hesabına katılmaz; test günü sayısı yön örneklemiyle aynı olmayabilir. Bugünkü tahminin güven yüzdesi değildir.{metrics && !metrics.evaluationVersion ? ' Eski OOF ölçümü; bağımsız kalibrasyon doğrulanmadı.' : ''}</InfoTooltip></span><strong>{metrics?.direction != null ? `%${(metrics.direction * 100).toFixed(1)}` : '—'}</strong><small>{metrics ? `${metrics.activeFraction != null ? `Görüş oranı %${(metrics.activeFraction * 100).toFixed(1)} · ` : ''}${metrics.oofRows} test günü${metrics.directionalRows != null ? ` · ${metrics.directionalRows} yön örneği` : ''}` : 'Model karnesi bekleniyor'}</small></div>
    </div>
    {available && <p className="model-update">Hesaplama referansı: {money(forecast.price)}{baseFrame ? ` · ${FRAME[baseFrame]}` : ''}{forecast.predictionTimestamp ? ` · ${new Date(forecast.predictionTimestamp).toLocaleString('tr-TR')}` : ''}. Canlı spot kotasyonundan ayrı bir senaryodur.</p>}
    {forecast.status === 'STALE_DATA' && <p className="model-update" role="status">Girdilerin kaynak tarihi 7 takvim gününden eski; model görünümü kapatıldı.</p>}
    {clipped.length > 0 && <p className="model-update" role="status">Eğitim dağılımı dışında kalan girdiler: {clipped.join(', ')}. Bu tanısal eşik doğrulanmış bir güven skoru değildir.</p>}
    {modelStatus === 'loading' && <p className="model-update" role="status">{hasForecast ? 'Son model sonucu gösteriliyor · güncelleniyor…' : 'Model hesaplanıyor…'}</p>}
  </section>;
}

export default ForecastCards;
