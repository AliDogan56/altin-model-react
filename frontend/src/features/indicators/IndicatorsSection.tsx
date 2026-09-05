import { Fragment, useState } from 'react';
import Collapsible from '../../components/Collapsible';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { money } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

const explanations: Record<string, string> = {
  RSI: 'Son 14 günlük fiyat hareketlerinin göreli gücünü gösterir. Aşırı alım ve aşırı satım bölgeleri, tek başına fiyatın döneceği anlamına gelmez.',
  Stochastic: 'Kapanışın son 14 günün en yüksek ve en düşük fiyatına göre konumunu gösterir. %D, kısa dönemli yumuşatılmış karşılaştırma çizgisidir.',
  Williams: 'Kapanışın son 14 günlük fiyat aralığındaki konumunu −100 ile 0 arasında gösterir. Uç bölgeler trend boyunca korunabilir.',
  CCI: 'Fiyatın 20 günlük ortalamasından sapmasını ölçer. Yüksek mutlak değerler ortalamadan daha belirgin bir uzaklığa işaret eder.',
  MACD: '12 ve 26 dönemlik üstel ortalamaların farkıdır. Durum, MACD değerinin 9 dönemlik sinyal çizgisine göre konumunu gösterir.',
  ADX: 'Trendin yönünden bağımsız olarak gücünü ölçer. +DI ve −DI değerleri yükseliş ve düşüş hareketlerini karşılaştırmaya yardımcı olur.',
  ATR: 'Son 14 günlük gerçek fiyat aralığını fiyatın yüzdesi olarak gösterir. Oynaklık durumu, tarihsel medyan ile karşılaştırılarak belirlenir.',
  ROC: 'Son kapanışın 12 gün önceki kapanışa göre yüzdesel değişimidir. Pozitif ve negatif değerler değişimin yönünü gösterir.',
};

function IndicatorsSection({ focus }: { focus?: string }) {
  const { tech } = useDashboard();
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  if (!tech) return null;

  const toggle = (name: string) => setExpanded(previous => {
    const next = new Set(previous);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    return next;
  });

  return (
    <Collapsible id="tech" anchor="feature-teknik" openByDefault={focus===PANEL_FEATURES.find(f=>f.anchor==="feature-teknik")?.slug} title={featureBy("feature-teknik").title} hint={featureBy("feature-teknik").summary} summary={`RSI ${tech.rows[0]?.value ?? '—'}`}>
      <section className="panel block tech-block indicator-panel" aria-labelledby="tech-title">
        <div className="market-table-head">
          <div><h2 id="tech-title">Teknik göstergeler</h2><p>Günlük XAU/USD · Gösterge durumları</p></div>
          <span className="market-table-help">Açıklama için göstergeyi açın</span>
        </div>
        <table className="indicator-table">
          <caption className="market-table-sr-only">Günlük XAU/USD teknik gösterge değerleri ve durumları</caption>
          <thead><tr><th scope="col">Gösterge</th><th scope="col">Değer</th><th scope="col">Durum</th></tr></thead>
          <tbody>{tech.rows.map((row, index) => {
            const isExpanded = expanded.has(row.name);
            const isDirectional = row.name.startsWith('MACD') || row.name.startsWith('ROC');
            const detailId = `indicator-explanation-${index}`;
            return <Fragment key={row.name}>
              <tr className={isExpanded ? 'is-expanded' : undefined}>
                <th scope="row"><button type="button" className="indicator-name" aria-expanded={isExpanded} aria-controls={detailId} onClick={() => toggle(row.name)}>
                  <span className="indicator-toggle" aria-hidden="true">{isExpanded ? '−' : '+'}</span>
                  <span>{row.name}{row.note && <small>{row.note}</small>}</span>
                </button></th>
                <td className="indicator-value">{row.value}</td>
                <td><span className={`indicator-state ${row.tone}`}>
                  {isDirectional && row.tone === 'up' && <span aria-hidden="true">↑ </span>}
                  {isDirectional && row.tone === 'down' && <span aria-hidden="true">↓ </span>}
                  {row.text}
                </span></td>
              </tr>
              <tr className="indicator-explanation" id={detailId} hidden={!isExpanded}>
                <td colSpan={3}><p>{explanations[row.name.split(' ')[0]] ?? 'Bu gösterge günlük XAU/USD fiyatlarından hesaplanır.'}</p></td>
              </tr>
            </Fragment>;
          })}</tbody>
        </table>
        <div className="indicator-subhead"><h3>Hareketli ortalamalar</h3><span>USD / ons</span></div>
        <table className="indicator-table indicator-table--averages">
          <caption className="market-table-sr-only">Basit ve üstel hareketli ortalamalar; son kapanışın basit ortalamaya göre konumu</caption>
          <thead><tr><th scope="col">Dönem</th><th scope="col"><abbr title="Basit hareketli ortalama">SMA</abbr></th><th scope="col"><abbr title="Üstel hareketli ortalama">EMA</abbr></th><th scope="col">Fiyatın konumu</th></tr></thead>
          <tbody>{tech.averages.map(a => <tr key={a.n}>
            <th scope="row">MA{a.n}</th>
            <td className="indicator-value">{a.sma == null ? '—' : money(a.sma)}</td>
            <td className="indicator-value">{a.ema == null ? '—' : money(a.ema)}</td>
            <td><span className={`indicator-state ${a.sma == null ? 'flat' : a.price >= a.sma ? 'up' : 'down'}`}>
              {a.sma == null ? 'Veri yetersiz' : <><span aria-hidden="true">{a.price >= a.sma ? '↑' : '↓'} </span>{a.price >= a.sma ? 'Fiyat üstünde' : 'Fiyat altında'}</>}
            </span></td>
          </tr>)}</tbody>
        </table>
        <p className="market-table-note">Fiyatın konumu, son kapanışın SMA değerine göre durumudur. Göstergeler alım-satım kararı üretmez; aşırı alım bölgesi yükselişin biteceği anlamına gelmez ve güçlü trendlerde gösterge uzun süre aynı bölgede kalabilir.</p>
      </section>
    </Collapsible>
  );
}

export default IndicatorsSection;
