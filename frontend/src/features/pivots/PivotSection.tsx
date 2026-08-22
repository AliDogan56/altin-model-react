import Collapsible from '../../components/Collapsible';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { money } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

function PivotSection({ focus }: { focus?: string }) {
  const { pivotPeriod, setPivotPeriod, pivotMethod, setPivotMethod, pivotLadder } = useDashboard();
  if (!pivotLadder) return null;
  return (
    <Collapsible id="pivot" anchor="feature-pivot" openByDefault={focus===PANEL_FEATURES.find(f=>f.anchor==="feature-pivot")?.slug} title={featureBy("feature-pivot").title} hint={featureBy("feature-pivot").summary} summary={pivotLadder.nearestUp?`İlk direnç ${pivotLadder.nearestUp}`:null}>
    <section className="panel block pivot-block" aria-labelledby="pivot-title">
    <div className="pivot-head">
    <div>
    <h2 id="pivot-title">Pivot seviyeleri</h2>
    <small>Önceki {pivotPeriod==='monthly'?'ayın':'haftanın'} yüksek/düşük/kapanışına standart formül uygulanarak bulunur ({pivotLadder.id}) — herkesin aynı hesapladığı seviyelerdir. Grafikteki destek-direnç şeritleri ise başka bir yoldan, fiyatın <b>fiilen döndüğü</b> noktalar kümelenerek çıkarılır; bu yüzden sayılar birebir tutmaz. İki yöntem aynı yeri gösteriyorsa seviye güçlü sayılır.</small></div>
    <div className="pivot-tools">
    <div className="segmented">{([['weekly','Haftalık'],['monthly','Aylık']] as const).map(([k,l])=>
    <button type="button" key={k} className={pivotPeriod===k?'active':''} aria-pressed={pivotPeriod===k} onClick={()=>setPivotPeriod(k)}>{l}</button>)}</div>
    <div className="segmented">{([['classic','Klasik'],['fib','Fibonacci']] as const).map(([k,l])=>
    <button type="button" key={k} className={pivotMethod===k?'active':''} aria-pressed={pivotMethod===k} onClick={()=>setPivotMethod(k)}>{l}</button>)}</div>
    </div>
    </div>
    <div className="pivot-ladder">
    {pivotLadder.items.map((item,index)=>
    <div key={item.name}>
    {index===pivotLadder.insertAt&&
    <div className="pivot-now"><span>şu an</span><b>{money(pivotLadder.price)}</b></div>}
    <div className={`pivot-row ${item.above?'up':'down'} ${item.name===pivotLadder.nearestUp||item.name===pivotLadder.nearestDown?'nearest':''}`}>
    <span className="pivot-name">{item.name}</span>
    <b>{money(item.value)}</b>
    <em>{item.distance>=0?'+':''}{(item.distance*100).toFixed(2)}%</em>
    </div>
    </div>)}
    {pivotLadder.insertAt===pivotLadder.items.length&&
    <div className="pivot-now"><span>şu an</span><b>{money(pivotLadder.price)}</b></div>}
    </div>
    {!pivotLadder.nearestUp&&<p className="pivot-alert">Fiyat bu dönemin <b>tüm seviyelerinin üzerinde</b>;
      dönem içinde direnç kalmadı, R3 artık ilk destek gibi okunur.</p>}
    {!pivotLadder.nearestDown&&<p className="pivot-alert">Fiyat bu dönemin <b>tüm seviyelerinin altında</b>;
      dönem içinde destek kalmadı, S3 artık ilk direnç gibi okunur.</p>}
    <p className="pivot-note">Fiyatın hemen üstündeki seviye ilk direnç, hemen altındaki ilk destek olarak okunur. Bu bir işlem önerisi değildir. <a href="/rehber/altin-destek-direnc">Destek ve direnç nasıl okunur?</a></p>
    </section>
    </Collapsible>
  );
}

export default PivotSection;
