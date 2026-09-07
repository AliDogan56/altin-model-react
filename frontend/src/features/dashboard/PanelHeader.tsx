import DataTimestamp from '../../components/ui/DataTimestamp';
import { money2, pct, tryRate, shortDate } from '../../lib/format';
import { useDashboard } from './DashboardContext';
import { GROUP_LABEL, TICKER_OPTIONS, optionOf, tickerValue, type TickerGroup } from './tickerOptions';
import { useTickerSlots } from './useTickerSlots';

const GROUPS: TickerGroup[] = ['market', 'macro'];

function PanelHeader({ demoted = false }: { demoted?: boolean }) {
  const { harem, usdTry, ziynet, spot, history, live, featuresDate, status, refresh, refreshForecast } = useDashboard();
  /* USD/TRY sabit; kalan üç yuva canlı piyasa ürünlerinden ya da makro girdilerden seçilir
     (`tickerOptions`), seçim tarayıcıda saklanır. */
  const { slots, setSlot } = useTickerSlots();
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
      {slots.map((id, index) => {
        const option = optionOf(id);
        return <div key={index}>
          <dt><label className="ticker-pick">
            <select aria-label={`${index + 2}. gösterge`} value={id} onChange={event => setSlot(index, event.target.value)}>
              {GROUPS.map(group => <optgroup key={group} label={GROUP_LABEL[group]}>
                {TICKER_OPTIONS.filter(o => o.group === group).map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
              </optgroup>)}
            </select>
          </label></dt>
          <dd>{tickerValue(id, { ziynet, live }) ?? '—'}</dd><small>{option?.note}</small>
        </div>;
      })}
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
