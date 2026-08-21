import { HORIZON_LABELS as LABELS } from '../../content/site';
import { openLegal } from '../../content/site';
import { model } from '../../data/artifact';
import { BAND_COVERAGE } from '../../domain/model/predict';
import { money, pct } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

function ForecastCards() {
  const { values, forecast } = useDashboard();
  return (
    <>
    <div className="cards three" id="feature-tahmin">{model.horizons.map((h,j)=>({h,j})).filter(x=>x.h!==7).map(({h,j})=>
    <article className="panel card" key={h}><span>{LABELS[h]}</span><strong>{money(values.price*(1+forecast.mean[j]))}</strong><b className={forecast.mean[j]>=0?'positive':'negative'}>{forecast.mean[j]>=0?'▲':'▼'} {pct(forecast.mean[j])}</b>
    <small>%{BAND_COVERAGE} bant<br/>{money(values.price*(1+forecast.mean[j]-forecast.err[j]))} – {money(values.price*(1+forecast.mean[j]+forecast.err[j]))}</small></article>)}</div>
            <p className="inline-legal">Gösterilen tahminler istatistiksel kestirimdir; yatırım danışmanlığı kapsamında değildir ve kâr garantisi sunmaz. <button type="button" className="link-btn" onClick={openLegal}>Yasal uyarının tamamı</button></p></>
  );
}

export default ForecastCards;
