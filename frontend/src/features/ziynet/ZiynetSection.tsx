import { featureBy } from '../../content/panel';
import { pct, tryMoney } from '../../lib/format';
import { ZIYNET } from '../../services/realtime/harem';
import { useDashboard } from '../dashboard/DashboardContext';

function ZiynetSection() {
  const { ziynet, zones } = useDashboard();
  const { band } = zones;
  return (
    <section id="feature-ziynet" className="panel block gram-block" aria-labelledby="gram-title">
    <div className="gram-head">
    <h2 id="gram-title">{featureBy("feature-ziynet").title}</h2>
    <small>Canlı piyasa kotasyonu; işçilik ve satıcı marjı fiyatın içindedir. Yüzde, önceki kapanışa göre satış fiyatındaki değişimdir.</small></div>
    <div className="gram-grid">
    {ZIYNET.filter(([code])=>ziynet[code]).map(([code,label])=>{
    const q=ziynet[code];
    /* Harem'in kapanis alanı bazı üründe bozuk geliyor: Yeni Ata gün
    zirvesindeyken önceki kapanışı aralığın %65 üstünde bildiriyor ve
    -%2,1 çıkıyor; neredeyse aynı ürün olan Tam altın ise +%2,3.
    Aşağı boşlukla açılış normaldir (kapanış aralığın altında kalır),
    kapanışın aralığın belirgin üstünde olması ise tutarsızlık işaretidir. */
    const band=q.high-q.low;
    const trusted=q.prev>0&&band>0&&q.prev>=q.low-1.5*band&&q.prev<=q.high+0.25*band;
    const change=trusted?q.satis/q.prev-1:0;
    const range=q.high-q.low;
    const at=range>0?Math.min(100,Math.max(0,(q.satis-q.low)/range*100)):50;
    return <article className={`quote ${trusted?(change>=0?'up':'down'):'flat'}`} key={code}>
    <header><span>{label}</span>
    {trusted&&<b className={change>=0?'positive':'negative'}>{change>=0?'▲':'▼'} {pct(Math.abs(change))}</b>}
    </header>
    <strong key={q.satis} className={`tick-${q.dir||'flat'}`}>{tryMoney(q.satis)}</strong>
    <small>Alış {tryMoney(q.alis)} · Makas {tryMoney(q.satis-q.alis)}</small>
    {range>0&&<div className="quote-range" title={`Gün aralığı ${tryMoney(q.low)} – ${tryMoney(q.high)}`}>
    <i style={{left:`${at}%`}}/>
    <u>{tryMoney(q.low)}</u><em>{tryMoney(q.high)}</em>
    </div>}
    </article>;
    })}
    </div>
    <p className="gram-note">Bu fiyatlar ons ve kurdan nasıl türer: <a href="/rehber/gram-altin-fiyati-nasil-belirlenir">Gram altın fiyatı nasıl belirlenir?</a> · <a href="/rehber/ceyrek-altin-kac-gram">Çeyrek altın kaç gram?</a> · <a href="/rehber/altin-makasi-nedir">Alış-satış makası nedir?</a></p>
    </section>
  );
}

export default ZiynetSection;
