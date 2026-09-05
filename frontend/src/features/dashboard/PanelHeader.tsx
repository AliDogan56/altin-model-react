import DataTimestamp from '../../components/ui/DataTimestamp';
import { money2, pct, tryRate, tryMoney, shortDate } from '../../lib/format';
import { useDashboard } from './DashboardContext';

function PanelHeader({ demoted = false }: { demoted?: boolean }) {
  const { harem, usdTry, ziynet, spot, history, live, featuresDate, status, refresh, refreshForecast } = useDashboard();
  const price = harem.satis ?? (spot.live ? spot.price : null);
  // Daily close-to-close movement; kept separate from the live quote.
  const latest = history.at(-1), previous = history.at(-2);
  const change = spot.live && latest && previous ? latest[1] / previous[1] - 1 : null;
  const changeUsd = latest && previous ? latest[1] - previous[1] : null;
  const Heading = demoted ? 'h2' : 'h1';
  return <section id="panel" className="market-overview" aria-labelledby="market-title">
    <div className="market-price" id="icerik" tabIndex={-1}>
      <div className="market-title-line"><Heading id="market-title">Ons altın</Heading><span className="instrument-code">XAU / USD</span></div>
      <div className="market-price-line"><strong>{price ? money2(price) : <span className="value-placeholder">—</span>}</strong><span className="price-unit">USD / ons</span></div>
      <div className="market-daily">
        {change != null && changeUsd != null
          ? <><b className={change >= 0 ? 'positive' : 'negative'}>{change >= 0 ? '↑ +' : '↓ −'}{money2(Math.abs(changeUsd))} <span>({pct(change)})</span></b><span>{shortDate(latest![0])} · günlük kapanış hareketi</span></>
          : <span>Günlük hareket verisi bekleniyor</span>}
      </div>
    </div>
    <dl className="market-ticker" aria-label="Piyasa ve makro özeti">
      <div><dt>USD / TRY</dt><dd>{usdTry.satis ? `₺${tryRate(usdTry.satis)}` : '—'}</dd><small>Canlı döviz kuru</small></div>
      <div><dt>Gram altın</dt><dd>{ziynet.ALTIN ? tryMoney(ziynet.ALTIN.satis) : '—'}</dd><small>995 · satış fiyatı</small></div>
      <div><dt>Dolar endeksi</dt><dd>{live.dollar_return_5d != null ? pct(live.dollar_return_5d) : '—'}</dd><small>Geniş dolar · 5 gün</small></div>
      <div><dt>Reel faiz</dt><dd>{live.real_yield_change_5d != null ? `${live.real_yield_change_5d >= 0 ? '+' : ''}${live.real_yield_change_5d.toFixed(2)} puan` : '—'}</dd><small>10 yıllık · 5 gün</small></div>
    </dl>
    <div className="market-data-line">
      <DataTimestamp time={harem.time ?? spot.time} live={harem.live} updating={status.busy}/>
      <span className="market-macro-date">Makro veri: {featuresDate ? shortDate(featuresDate, true) : 'bekleniyor'}</span>
      <button className="quiet-button" type="button" disabled={status.busy} onClick={() => { void refresh(); refreshForecast(); }}>
        <span aria-hidden="true">↻</span> {status.busy ? 'Güncelleniyor' : 'Yenile'}
      </button>
    </div>
  </section>;
}

export default PanelHeader;
