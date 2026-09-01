import { featureBy } from '../../content/panel';
import { buildZiynetRows, pureGramPrice, type ZiynetRow } from '../../domain/ziynet';
import { pct, pct2, tryMoney } from '../../lib/format';
import { ZIYNET } from '../../services/realtime/harem';
import { useDashboard } from '../dashboard/DashboardContext';

const ORDER = ZIYNET.map(([code]) => code);

const grams = (value: number) => `${value.toFixed(3).replace(/\.?0+$/, '').replace('.', ',')} gr`;

function Tile({ row }: { row: ZiynetRow }) {
  return (
    <article className="quote" key={row.code}>
      <header>
        <span className="quote-name">{row.label}</span>
        <em className="quote-content">{grams(row.pureGrams)} saf altın</em>
      </header>

      <strong key={row.satis} className={`quote-price tick-${row.dir || 'flat'}`}>{tryMoney(row.satis)}</strong>
      <div className="quote-line">
        <span>Alış <b>{tryMoney(row.alis)}</b></span>
        <span>Makas <b>{tryMoney(row.satis - row.alis)}</b> ({pct2(row.spreadPct)})</span>
      </div>

      {row.rawValue != null && row.premium != null && <div className="quote-breakdown">
        <div><span>Ham altın değeri</span><b>{tryMoney(row.rawValue)}</b></div>
        <div><span>İşçilik + satıcı payı</span>
          <b className={row.premium >= 0 ? 'warn' : 'positive'}>
            {row.premium >= 0 ? '+' : '−'}{pct2(Math.abs(row.premium))}</b></div>
        <div className="premium-bar">
          <i style={{ width: `${Math.min(100, Math.max(1, Math.abs(row.premium) * 100 / 0.06 * 100))}%` }}/>
        </div>
      </div>}

      {row.change != null && <p className="quote-change">
        Önceki kapanışa göre <b className={row.change >= 0 ? 'positive' : 'negative'}>
          {row.change >= 0 ? '▲' : '▼'} {pct(Math.abs(row.change))}</b></p>}
    </article>
  );
}

function ZiynetSection() {
  const { ziynet, harem, usdTry } = useDashboard();
  const ons = harem.satis ?? 0;
  const kur = usdTry.satis ?? 0;
  const rows = buildZiynetRows(ziynet, ons, kur, ORDER);
  const gramPrice = pureGramPrice(ons, kur);
  const missingChange = rows.filter(row => row.change == null).length;

  return (
    <section id="feature-ziynet" className="panel block gram-block" aria-labelledby="gram-title">
      <div className="gram-head">
        <div>
          <h2 id="gram-title">{featureBy('feature-ziynet').title}</h2>
          <small>Her ürünün fiyatı, içindeki saf altının değeri ve üzerine binen işçilik-marj payı.
            Fiyatlar canlı piyasa kotasyonudur.</small>
        </div>
        {gramPrice != null && <div className="gram-basis">
          <span>1 gram saf altın</span><b>{tryMoney(gramPrice)}</b>
          <small>canlı ons × USD/TL ÷ 31,1035</small>
        </div>}
      </div>

      <div className="gram-grid">{rows.map(row => <Tile key={row.code} row={row}/>)}</div>

      <p className="gram-note">
        {gramPrice == null && <b>Kur akışı beklendiği için ham değer ve işçilik payı hesaplanamıyor. </b>}
        {missingChange > 0 && `${missingChange} üründe günlük değişim gösterilmiyor; kaynağın bildirdiği önceki kapanış gün aralığıyla bağdaşmıyor. `}
        Bu fiyatlar ons ve kurdan nasıl türer:{' '}
        <a href="/rehber/ons-gram-altin-hesaplama">Ons’tan gram altına hesaplama</a> ·{' '}
        <a href="/rehber/ceyrek-altin-kac-gram">Çeyrek altın kaç gram?</a> ·{' '}
        <a href="/rehber/altin-makasi-nedir">Alış-satış makası nedir?</a>
      </p>
    </section>
  );
}

export default ZiynetSection;
