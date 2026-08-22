import { HORIZON_LABELS as LABELS } from '../../content/site';
import { openLegal } from '../../content/site';
import { BAND_COVERAGE } from '../../domain/model/predict';
import { money, pct } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

function ForecastCards() {
  const { values, forecast, horizonDays, setHorizonDays, modelStatus, confident, weights } = useDashboard();
  const available = modelStatus === 'live';
  return (
    <>
    <div className="cards" id="feature-tahmin">{forecast.horizons.map((h,j)=>({h,j})).map(({h,j})=>{
      /* Ağırlığı eşiğin altındaki ufukta ağın katkısı neredeyse tamamen kısılmıştır;
         sıfıra yakın çıktı "tahmin" gibi değil "görüş yok" olarak sunulur. */
      const sure = available && confident[j] !== false;
      return <button type="button" className={`panel card forecast-card ${horizonDays===h?'selected':''} ${available&&!sure?'no-view':''}`} key={h}
        aria-pressed={horizonDays===h} onClick={()=>setHorizonDays(h)}>
        <span>{LABELS[h]}</span>
        <strong>{!available?'—':sure?money(values.price*(1+forecast.mean[j])):'Görüş yok'}</strong>
        <b className={sure?(forecast.mean[j]>=0?'positive':'negative'):undefined}>
          {!available?'Tahmin bekleniyor':sure?`${forecast.mean[j]>=0?'▲':'▼'} ${pct(forecast.mean[j])}`:`ağırlık ${(weights[j]??0).toFixed(2)}`}</b>
        <small>{!available?'Aktif model sonucu olmadan fiyat gösterilmez.'
          :sure?<>%{BAND_COVERAGE} olasılık bandı<br/>{money(values.price*(1+forecast.mean[j]-forecast.err[j]))} – {money(values.price*(1+forecast.mean[j]+forecast.err[j]))}</>
          :'Model bu vadede sıfır getiri kuralını anlamlı biçimde yenemiyor; yön bildirmiyor.'}</small>
        <em>{modelStatus==='loading'?'Model güncelleniyor…':modelStatus==='fallback'?'Model servisi çevrimdışı':horizonDays===h?'Grafikte gösteriliyor':'Grafikte göster'}</em></button>;})}</div>
            <p className="inline-legal">Gösterilen tahminler istatistiksel kestirimdir; yatırım danışmanlığı kapsamında değildir ve kâr garantisi sunmaz. <button type="button" className="link-btn" onClick={openLegal}>Yasal uyarının tamamı</button></p></>
  );
}

export default ForecastCards;
