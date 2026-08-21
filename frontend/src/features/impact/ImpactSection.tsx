import Collapsible from '../../components/Collapsible';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { model } from '../../data/artifact';
import { pct } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

function ImpactSection({ focus }: { focus?: string }) {
  const { impacts } = useDashboard();
  return (
    <Collapsible id="impact" anchor="feature-katki" openByDefault={focus===PANEL_FEATURES.find(f=>f.anchor==="feature-katki")?.slug} title={featureBy("feature-katki").title} hint={featureBy("feature-katki").summary} summary={impacts.rows[0]?impacts.rows[0].name:null}>
    <section className="panel block impact-block" aria-labelledby="impact-title">
    <div className="impact-head">
    <h2 id="impact-title">1 aylık tahmine parametre katkısı</h2><p>Her satır şunu ölçer: <b>o gösterge bugünkü değerinden uzun dönem ortalamasına çekilseydi, 1 aylık tahmin kaç puan değişirdi.</b> Pozitif değer, göstergenin bugünkü seviyesinin tahmini yukarı çektiği anlamına gelir. Yanındaki <em>sd</em> rozeti göstergenin ortalamadan kaç standart sapma uzakta olduğunu söyler.</p>
    <p className="impact-caveat">Satırların toplamı alttaki parametre katkısına eşit çıkmaz: burada modelin 31 girdisinden yalnız en çok konuşulan 8'i listeleniyor ve model doğrusal olmadığı için etkiler birbirinden bağımsız değil.</p></div>
    <div className="impact-grid">{impacts.rows.map(x=>
    <div className="impact" key={x.key}><span>{x.name}<em className={Math.abs(x.z)>=1?'far':undefined}>{x.z>=0?'+':''}{x.z.toFixed(1)} sd</em></span>
    <div><i className={x.value>=0?'pos':'neg'} style={{width:`${Math.max(3,x.share*100)}%`}}/></div><b className={x.value>=0?'positive':'negative'}>{x.value>=0?'+':''}{(x.value*100).toFixed(2)} p</b></div>)}</div>
    <div className="impact-sum">
    <div><span>Sabit taban</span><b>{pct(impacts.constant)}</b>
    <small>tüm göstergeler ortalamadayken modelin verdiği tahmin</small></div>
    <div><span>Parametre katkısı</span><b className={impacts.total>=0?'positive':'negative'}>{impacts.total>=0?'+':''}{(impacts.total*100).toFixed(2)} p</b>
    <small>bugünkü sapmaların toplam etkisi</small></div>
    <div className="total"><span>1 aylık tahmin</span><b>{pct(impacts.here)}</b>
    <small>sabit taban + parametre katkısı</small></div></div></section>
    </Collapsible>
  );
}

export default ImpactSection;
