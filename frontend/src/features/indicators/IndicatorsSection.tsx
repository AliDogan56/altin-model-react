import Collapsible from '../../components/Collapsible';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { money } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

function IndicatorsSection({ focus }: { focus?: string }) {
  const { tech } = useDashboard();
  return (
    <Collapsible id="tech" anchor="feature-teknik" openByDefault={focus===PANEL_FEATURES.find(f=>f.anchor==="feature-teknik")?.slug} title={featureBy("feature-teknik").title} hint={featureBy("feature-teknik").summary} summary={`RSI ${tech.rows[0].value}`}>
    <section className="panel block tech-block" aria-labelledby="tech-title">
    <div className="pivot-head">
    <div>
    <h2 id="tech-title">Teknik göstergeler</h2>
    <small>Günlük PAXG/USDT mumlarından hesaplanır. Göstergenin bulunduğu durum yazılır; bilinçli olarak alım-satım kararı üretilmez — aşırı alım bölgesi yükselişin biteceği anlamına gelmez, güçlü trendlerde gösterge uzun süre orada kalabilir.</small></div></div>
    <div className="tech-grid">
    {tech.rows.map(row=>
    <div className="tech-row" key={row.name}>
    <span>{row.name}{row.note&&<em>{row.note}</em>}</span>
    <b>{row.value}</b>
    <i className={`tech-state ${row.tone}`}>{row.text}</i>
    </div>)}
    </div>
    <h3 className="tech-sub">Hareketli ortalamalar</h3>
    <div className="tech-grid ma">
    {tech.averages.map(a=>
    <div className="tech-row" key={a.n}>
    <span>MA{a.n}<em>EMA {money(a.ema)}</em></span>
    <b>{money(a.sma)}</b>
    <i className={`tech-state ${a.price>=a.sma?'up':'down'}`}>{a.price>=a.sma?'Fiyat üstünde':'Fiyat altında'}</i>
    </div>)}
    </div>
    </section>
    </Collapsible>
  );
}

export default IndicatorsSection;
