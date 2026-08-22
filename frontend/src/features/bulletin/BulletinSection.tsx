import Collapsible from '../../components/Collapsible';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { pct, shortDate } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

function BulletinSection({ focus }: { focus?: string }) {
  const { news, features, featuresDate } = useDashboard();
  return (
    <Collapsible id="bulletin" anchor="feature-bulten" openByDefault={focus===PANEL_FEATURES.find(f=>f.anchor==="feature-bulten")?.slug} title={featureBy("feature-bulten").title} hint={featureBy("feature-bulten").summary} summary={news.length?`${news.length} haber`:null}>
    <section className="panel block">
    <h2>Altın etki bülteni</h2>
    <div className="bulletins">
    <div>
    <h3>Parametre özeti</h3>
    <p><b>Reel faiz:</b> 5 günlük {features.real_yield_change_5d>=0?'+':''}{features.real_yield_change_5d.toFixed(2)} puan.</p>
    <p><b>Dolar:</b> 5 günlük {pct(features.dollar_return_5d)}.</p>
    <p><b>VIX:</b> 5 günlük {features.vix_change_5d>=0?'+':''}{features.vix_change_5d.toFixed(2)}.</p>
    <p className="bulletin-asof">{featuresDate?`${shortDate(featuresDate,true)} tarihli veri setine göre.`:''} Makro serilerin
      yayın gecikmesi 1–6 gündür; sıfır değişim, seride yeni gözlem olmadığı anlamına da gelebilir.</p></div>
    <div>
    <h3>Canlı haberler</h3>{news.slice(0,5).map((n)=><a key={n.url||n.title} href={n.url} target="_blank" rel="noreferrer">{n.title}<small>{n.source}</small></a>)}</div></div></section>
    </Collapsible>
  );
}

export default BulletinSection;
