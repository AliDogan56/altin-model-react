import { useMinVisible } from '../../app/useMinVisible';
import Spinner from '../../components/Spinner';
import TickSparkline from '../../components/TickSparkline';
import { money2, tryRate } from '../../lib/format';
import { useDashboard } from './DashboardContext';

/**
 * `demoted`: panel sayfasında h1'i panelin kendi başlığı taşır, bu başlık h2'ye
 * iner. Sayfada tek h1 kalsın ve 11 panel URL'i aynı h1'i paylaşmasın diye.
 */
function PanelHeader({ demoted = false }: { demoted?: boolean }) {
  const { harem, usdTry, haremTicks, status, refresh, refreshForecast, version, modelStatus } = useDashboard();
  /* Akış çoğu zaman bir saniyeden hızlı kuruluyor; tamponsuz spinner tek
     karede kaybolup dolumu göstermiyordu. */
  const onsBusy = useMinVisible(!harem.live);
  const fxBusy = useMinVisible(!usdTry.live);
  const fetching = useMinVisible(!!status.busy);
  return (
    <header id="panel">
    <div id="icerik"><span className="eyebrow">Özgün Altın Tahmin Modeli</span>{demoted
      ? <h2>Canlı Ons Altın Tahmin ve Senaryo Analiz Paneli</h2>
      : <h1>Canlı Ons Altın Tahmin ve Senaryo Analiz Paneli</h1>}<p>Tahmin, eğitim ve hata ölçümü doğrudan XAU/USD günlük verisiyle yapılır.</p></div>
    <div className="header-market">
    <div className="live-price ons-price"><span>{onsBusy?<Spinner size="xs"/>:<i className="ok"/>}ONS / XAUUSD</span><strong>{harem.satis&&!onsBusy?money2(harem.satis):<Spinner size="sm" label="Bağlanıyor…" inline/>}</strong>
    <div className="bid-ask"><b>Alış {harem.alis?money2(harem.alis):'—'}</b><b>Satış {harem.satis&&!onsBusy?money2(harem.satis):'—'}</b></div><TickSparkline ticks={haremTicks}/>
    <small>{!onsBusy&&harem.time?`Son fiyat ${harem.time.toLocaleTimeString('tr-TR')}`
      :<Spinner size="xs" label={harem.time?'Akış yeniden kuruluyor…':'Canlı ons akışına bağlanılıyor…'} inline/>}</small></div>
    <div className="live-price fx-price"><span>{fxBusy?<Spinner size="xs"/>:<i className="ok"/>}USD / TL</span><strong>{usdTry.satis&&!fxBusy?`₺${tryRate(usdTry.satis)}`:<Spinner size="sm" label="Bağlanıyor…" inline/>}</strong>
    <div className="bid-ask"><b>Alış {usdTry.alis?`₺${tryRate(usdTry.alis)}`:'—'}</b><b>Satış {usdTry.satis&&!fxBusy?`₺${tryRate(usdTry.satis)}`:'—'}</b></div>
    <small>{!fxBusy&&usdTry.time?`Son kur ${usdTry.time.toLocaleTimeString('tr-TR')}`
      :<Spinner size="xs" label={usdTry.time?'Akış yeniden kuruluyor…':'Canlı kura bağlanılıyor…'} inline/>}</small></div>
    <div className="status"><b>{version || (modelStatus==='fallback'?'Model servisi çevrimdışı':'XAU/USD modeli')}</b><span>7 · 14 · 30 günlük</span><button type="button" onClick={()=>{ void refresh(); refreshForecast(); }}>{fetching?<Spinner size="sm" inline/>:<i className={status.type}/>}{status.text}</button></div></div></header>
  );
}

export default PanelHeader;
