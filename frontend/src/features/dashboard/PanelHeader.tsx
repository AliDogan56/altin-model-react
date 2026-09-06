import DataTimestamp from '../../components/ui/DataTimestamp';
import { sessionStaleAfterMs } from './useTechnical';
import { FRAME, STATUS_TEXT } from '../../content/technical';
import { money2, pct, tryRate, tryMoney, shortDate } from '../../lib/format';
import { useDashboard } from './DashboardContext';

/** Blok durum cümlesi; `OK` ve bilinmeyen anahtar için `null` (sunucu yeni bir
 *  durum eklerse yanlış cümle yazmak yerine genel bekleme metnine düşülür). */
const statusText = (status: string | null | undefined): string | null =>
  status ? (STATUS_TEXT as Record<string, string | null>)[status] ?? null : null;

function PanelHeader({ demoted = false }: { demoted?: boolean }) {
  const { harem, usdTry, ziynet, live, featuresDate, status, refresh, refreshForecast, reference, dailyChange, technical, sessionMeta } = useDashboard();
  /* Büyük fiyat yalnız Harem kotasyonu: canlı spot, hiçbir hesaba girmez.
     Teknik paketin referansı (GC=F) ayrı satırda kendi çerçevesiyle yazılır;
     ikisini aynı etiket altında karıştırmak en yakın seviyeyi değiştiriyordu. */
  const price = harem.satis;
  const Heading = demoted ? 'h2' : 'h1';
  const referenceStatus = statusText(reference?.status);
  const dailyStatus = statusText(technical?.status.daily);
  return <section id="panel" className="market-overview" aria-labelledby="market-title">
    <div className="market-price">
      <div className="market-title-line"><Heading id="market-title">Ons altın</Heading><span className="instrument-code">XAU / USD</span></div>
      <div className="market-price-line"><strong>{price ? money2(price) : <span className="value-placeholder">—</span>}</strong><span className="price-unit">USD / ons · Canlı spot · Harem</span></div>
      <div className="market-daily">
        {dailyChange
          ? <><b className={dailyChange.usd >= 0 ? 'positive' : 'negative'}>{dailyChange.usd >= 0 ? '↑ +' : '↓ −'}{money2(Math.abs(dailyChange.usd))}{dailyChange.pct != null && <span> ({pct(dailyChange.pct)})</span>}</b>
            <span>{shortDate(dailyChange.date)} · {shortDate(dailyChange.previousDate)} kapanışına göre</span></>
          : <span>{dailyStatus ?? 'Günlük hareket verisi bekleniyor'}</span>}
      </div>
      <div className="market-daily market-reference">
        {reference && reference.value != null
          ? <><span>Hesap referansı <b>{money2(reference.value)}</b> · {FRAME[reference.frame]}</span>
            <DataTimestamp time={reference.asOf ?? reference.dailyDate} label="Referans" staleAfterMs={sessionStaleAfterMs(sessionMeta)}/></>
          : <span>{referenceStatus ?? 'Hesap referansı bekleniyor'}</span>}
        {referenceStatus && reference?.value != null && <span>{referenceStatus}</span>}
      </div>
    </div>
    <dl className="market-ticker" aria-label="Piyasa ve makro özeti">
      <div><dt>USD / TRY</dt><dd>{usdTry.satis ? `₺${tryRate(usdTry.satis)}` : '—'}</dd><small>Canlı döviz kuru</small></div>
      <div><dt>Gram altın</dt><dd>{ziynet.ALTIN ? tryMoney(ziynet.ALTIN.satis) : '—'}</dd><small>995 · satış fiyatı</small></div>
      <div><dt>Dolar endeksi</dt><dd>{live.dollar_return_5d != null ? pct(live.dollar_return_5d) : '—'}</dd><small>Geniş dolar · 5 gün</small></div>
      <div><dt>Reel faiz</dt><dd>{live.real_yield_change_5d != null ? `${live.real_yield_change_5d >= 0 ? '+' : ''}${live.real_yield_change_5d.toFixed(2)} puan` : '—'}</dd><small>10 yıllık · 5 gün</small></div>
    </dl>
    <div className="market-data-line">
      <DataTimestamp time={harem.time} live={harem.live} updating={status.busy}/>
      <span className="market-macro-date">Makro veri: {featuresDate ? shortDate(featuresDate, true) : 'bekleniyor'}</span>
      <button className="quiet-button" type="button" disabled={status.busy} onClick={() => { void refresh(); refreshForecast(); }}>
        <span aria-hidden="true">↻</span> {status.busy ? 'Güncelleniyor' : 'Yenile'}
      </button>
    </div>
  </section>;
}

export default PanelHeader;
