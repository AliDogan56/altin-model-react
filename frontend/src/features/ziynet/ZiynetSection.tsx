import { featureBy } from '../../content/panel';
import { buildZiynetRows, pureGramPrice, type ZiynetRow } from '../../domain/ziynet';
import { pct, pct2, tryMoney } from '../../lib/format';
import { ZIYNET } from '../../services/realtime/harem';
import { useDashboard } from '../dashboard/DashboardContext';

const ORDER = ZIYNET.map(([code]) => code);

const grams = (value: number) => `${value.toFixed(3).replace(/\.?0+$/, '').replace('.', ',')} gr`;

function DailyChange({ change }: { change: ZiynetRow['change'] }) {
  if (change == null) return <span className="market-table-muted" title="Kaynakta karşılaştırılabilir önceki kapanış bulunmuyor">—</span>;
  return <span className={`market-table-change ${change >= 0 ? 'is-positive' : 'is-negative'}`}>
    <span aria-hidden="true">{change >= 0 ? '↑' : '↓'}</span> {pct(Math.abs(change))}
  </span>;
}

function Premium({ premium }: { premium: ZiynetRow['premium'] }) {
  if (premium == null) return <span className="market-table-muted">—</span>;
  return <span className={`market-table-premium ${premium >= 0 ? 'is-premium' : 'is-positive'}`}>
    {premium >= 0 ? '+' : '−'}{pct2(Math.abs(premium))}
  </span>;
}

function ProductDetails({ row }: { row: ZiynetRow }) {
  return (
    <details className="market-product">
      <summary>
        <span className="market-product-name"><strong>{row.label}</strong><small>{grams(row.pureGrams)} saf altın</small></span>
        <span className="market-product-price"><strong className={`market-table-price tick-${row.dir || 'flat'}`}>{tryMoney(row.satis)}</strong><DailyChange change={row.change}/></span>
        <span className="market-product-toggle" aria-hidden="true">+</span>
      </summary>
      <dl className="market-product-details">
        <div><dt>Alış</dt><dd>{tryMoney(row.alis)}</dd></div>
        <div><dt>Satış</dt><dd>{tryMoney(row.satis)}</dd></div>
        <div><dt>Alış-satış makası</dt><dd>{tryMoney(row.satis - row.alis)} <small>({pct2(row.spreadPct)})</small></dd></div>
        <div><dt>Saf altın değeri</dt><dd>{row.rawValue == null ? '—' : tryMoney(row.rawValue)}</dd></div>
        <div><dt>Prim / işçilik</dt><dd><Premium premium={row.premium}/></dd></div>
      </dl>
    </details>
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
    <section id="feature-ziynet" className="panel block gram-block market-prices" aria-labelledby="gram-title">
      <div className="market-table-head">
        <div>
          <h2 id="gram-title">{featureBy('feature-ziynet').title}</h2>
          <p>Canlı piyasa kotasyonları · Türk lirası</p>
        </div>
        {gramPrice != null && <div className="market-table-basis">
          <span>1 gram saf altın</span><b>{tryMoney(gramPrice)}</b>
          <small>canlı ons × USD/TL ÷ 31,1035</small>
        </div>}
      </div>

      <div className="market-table-desktop">
        <table className="market-table">
          <caption className="market-table-sr-only">Ziynet altın alış, satış, makas ve saf altın değeri karşılaştırması. Tutarlar Türk lirasıdır.</caption>
          <thead><tr>
            <th scope="col">Ürün</th><th scope="col">Alış</th><th scope="col">Satış</th>
            <th scope="col">Makas</th><th scope="col">Günlük değişim</th>
            <th scope="col">Saf altın değeri</th><th scope="col">Prim / işçilik</th>
          </tr></thead>
          <tbody>{rows.map(row => <tr key={row.code}>
            <th scope="row"><strong>{row.label}</strong><small>{grams(row.pureGrams)} saf altın</small></th>
            <td>{tryMoney(row.alis)}</td>
            <td className={`market-table-price tick-${row.dir || 'flat'}`}>{tryMoney(row.satis)}</td>
            <td>{tryMoney(row.satis - row.alis)}<small>{pct2(row.spreadPct)}</small></td>
            <td><DailyChange change={row.change}/></td>
            <td>{row.rawValue == null ? '—' : tryMoney(row.rawValue)}</td>
            <td><Premium premium={row.premium}/></td>
          </tr>)}</tbody>
        </table>
      </div>
      <div className="market-product-list">
        <div className="market-product-labels"><span>Ürün</span><span>Satış / günlük değişim</span></div>
        {rows.map(row => <ProductDetails key={row.code} row={row}/>)}
        {rows.length > 0 && <p className="market-table-help">Alış, makas ve işçilik detayları için ürünü açın.</p>}
      </div>
      {rows.length === 0 && <p className="market-table-empty" role="status">Ziynet fiyatları bekleniyor.</p>}

      <p className="market-table-note">
        {gramPrice == null && <b>Kur akışı beklendiği için ham değer ve işçilik payı hesaplanamıyor. </b>}
        {missingChange > 0 && `${missingChange} üründe günlük değişim gösterilmiyor; kaynağın bildirdiği önceki kapanış gün aralığıyla bağdaşmıyor. `}
        Prim / işçilik, satış fiyatının saf altın değerine göre farkıdır; işçilik ve satıcı payını birlikte içerir.{' '}
        Bu fiyatlar ons ve kurdan nasıl türer:{' '}
        <a href="/rehber/ons-gram-altin-hesaplama">Ons’tan gram altına hesaplama</a> ·{' '}
        <a href="/rehber/ceyrek-altin-kac-gram">Çeyrek altın kaç gram?</a> ·{' '}
        <a href="/rehber/altin-makasi-nedir">Alış-satış makası nedir?</a>
      </p>
    </section>
  );
}

export default ZiynetSection;
