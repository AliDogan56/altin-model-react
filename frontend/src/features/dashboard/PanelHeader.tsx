import TickSparkline from '../../components/TickSparkline';
import { model } from '../../data/artifact';
import { money2, tryRate } from '../../lib/format';
import { useDashboard } from './DashboardContext';

function PanelHeader() {
  const { spot, harem, usdTry, haremTicks, status, refresh } = useDashboard();
  return (
    <header id="panel">
    <div id="icerik"><span className="eyebrow">Özgün Altın Tahmin Modeli</span><h1>Canlı Ons Altın Tahmin ve Senaryo Analiz Paneli</h1><p>Tahmin ve eğitim referansı PAXG/USDT; ONS/XAUUSD yalnızca canlı piyasa karşılaştırmasıdır.</p></div>
    <div className="header-market">
    <div className="live-price token-price"><span><i className={spot.live?'ok':'warn'}/>PAXG / USDT</span><strong>{money2(spot.price)}</strong><b className={spot.change>=0?'positive':'negative'}>{spot.change>=0?'▲':'▼'} %{Math.abs(spot.change).toFixed(2)}</b>
    <small>{spot.time?`Son fiyat ${spot.time.toLocaleTimeString('tr-TR')}`:'Canlı akış bekleniyor'}</small></div>
    <div className="live-price ons-price"><span><i className={harem.live?'ok':'warn'}/>ONS / XAUUSD</span><strong>{harem.satis?money2(harem.satis):'Bağlanıyor…'}</strong>
    <div className="bid-ask"><b>Alış {harem.alis?money2(harem.alis):'—'}</b><b>Satış {harem.satis?money2(harem.satis):'—'}</b></div><TickSparkline ticks={haremTicks}/>
    <small>{harem.satis?`PAXG farkı ${(harem.satis-spot.price)>=0?'+':''}${money2(harem.satis-spot.price)}`:'Canlı ons akışı bekleniyor'}</small></div>
    <div className="live-price fx-price"><span><i className={usdTry.live?'ok':'warn'}/>USD / TL</span><strong>{usdTry.satis?`₺${tryRate(usdTry.satis)}`:'Bağlanıyor…'}</strong>
    <div className="bid-ask"><b>Alış {usdTry.alis?`₺${tryRate(usdTry.alis)}`:'—'}</b><b>Satış {usdTry.satis?`₺${tryRate(usdTry.satis)}`:'—'}</b></div>
    <small>{usdTry.time?`Son kur ${usdTry.time.toLocaleTimeString('tr-TR')}`:'Canlı kur bekleniyor'}</small></div>
    <div className="status"><b>Model {model.latestDate}</b><span>{model.rows.toLocaleString('tr-TR')} gözlem</span><button onClick={refresh}><i className={status.type}/>{status.text}</button></div></div></header>
  );
}

export default PanelHeader;
