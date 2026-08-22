import TickSparkline from '../../components/TickSparkline';
import { money2, tryRate } from '../../lib/format';
import { useDashboard } from './DashboardContext';

function PanelHeader() {
  const { harem, usdTry, haremTicks, status, refresh, refreshForecast, version, modelStatus } = useDashboard();
  return (
    <header id="panel">
    <div id="icerik"><span className="eyebrow">Özgün Altın Tahmin Modeli</span><h1>Canlı Ons Altın Tahmin ve Senaryo Analiz Paneli</h1><p>Tahmin, eğitim ve hata ölçümü doğrudan XAU/USD günlük verisiyle yapılır.</p></div>
    <div className="header-market">
    <div className="live-price ons-price"><span><i className={harem.live?'ok':'warn'}/>ONS / XAUUSD</span><strong>{harem.satis?money2(harem.satis):'Bağlanıyor…'}</strong>
    <div className="bid-ask"><b>Alış {harem.alis?money2(harem.alis):'—'}</b><b>Satış {harem.satis?money2(harem.satis):'—'}</b></div><TickSparkline ticks={haremTicks}/>
    <small>{harem.time?`Son fiyat ${harem.time.toLocaleTimeString('tr-TR')}`:'Canlı ons akışı bekleniyor'}</small></div>
    <div className="live-price fx-price"><span><i className={usdTry.live?'ok':'warn'}/>USD / TL</span><strong>{usdTry.satis?`₺${tryRate(usdTry.satis)}`:'Bağlanıyor…'}</strong>
    <div className="bid-ask"><b>Alış {usdTry.alis?`₺${tryRate(usdTry.alis)}`:'—'}</b><b>Satış {usdTry.satis?`₺${tryRate(usdTry.satis)}`:'—'}</b></div>
    <small>{usdTry.time?`Son kur ${usdTry.time.toLocaleTimeString('tr-TR')}`:'Canlı kur bekleniyor'}</small></div>
    <div className="status"><b>{version || (modelStatus==='fallback'?'Model servisi çevrimdışı':'XAU/USD modeli')}</b><span>7 · 14 · 30 günlük</span><button type="button" onClick={()=>{ void refresh(); refreshForecast(); }}><i className={status.type}/>{status.text}</button></div></div></header>
  );
}

export default PanelHeader;
