import { useState } from 'react';
import { featureBy } from '../../content/panel';
import { model } from '../../data/artifact';
import { money, shortDate } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';
import ForecastChart from './ForecastChart';

const TABLE_ID = 'gunluk-tahmin-tablosu';

function ChartSection() {
  const {
    history, spot, harem, rangeDays, setRangeDays, horizonDays, setHorizonDays,
    showBand, setShowBand, showLevels, setShowLevels, showOrigin, setShowOrigin, showSR, setShowSR,
    forecast, originForecast, forecastTable, zones,
  } = useDashboard();
  const { buy, sell, stop } = zones;
  /* Tablo 90–180 satırın çoğu boş "—" ile açılıyordu; varsayılan olarak yalnız
     vadesi dolan günler listelenir, tamamı istendiğinde açılır. */
  const [onlySettled, setOnlySettled] = useState(true);

  const settled = forecastTable.filter(row => row.real != null);
  const rows = onlySettled ? settled : forecastTable;

  return (
    <section id="feature-grafik" className="panel block chart-block">
      <div className="chart-head">
        <div>
          <h2>{featureBy('feature-grafik').title}</h2>
          <p>Solda gerçekleşen, sağda tahmin. Kesikli çizgi modelin {model.latestDate} tahmini;
            geçmiş bir güne gelince o günün gerçekleşen değeri ve modelin sapması görünür.</p>
        </div>
        <div className="chart-tools">
          <div className="tool-group"><span>Tahmin</span>
            <div className="segmented">{([[30, '1 Ay'], [90, '3 Ay'], [180, '6 Ay']] as [number, string][]).map(([n, label]) =>
              <button key={n} className={horizonDays === n ? 'active' : ''} onClick={() => setHorizonDays(n)}>{label}</button>)}</div>
          </div>
          <div className="tool-group"><span>Geçmiş</span>
            <div className="segmented">{[30, 90, 180, 260].map(n =>
              <button key={n} className={rangeDays === n ? 'active' : ''} onClick={() => setRangeDays(n)}>{n === 260 ? '1Y' : `${n}G`}</button>)}</div>
          </div>
        </div>
      </div>

      <ForecastChart
        forecast={forecast} history={history} rangeDays={rangeDays} horizonDays={horizonDays}
        showBand={showBand} showLevels={showLevels} showOrigin={showOrigin} showSR={showSR}
        originForecast={originForecast} describedById={TABLE_ID}
        onToggle={key => {
          if (key === 'band') setShowBand(v => !v);
          else if (key === 'origin') setShowOrigin(v => !v);
          else if (key === 'sr') setShowSR(v => !v);
          else setShowLevels(v => !v);
        }}
        levels={{ buy, sell, stop }} spot={{ ...spot, price: harem.satis || spot.price }} tokenSpot={spot}/>

      <details className="daily-table" id={TABLE_ID}>
        <summary>
          <i className="origin-key" aria-hidden="true"/>
          {shortDate(model.latestDate, true)} tahmini · gerçekleşenle karşılaştırma
          <b>{settled.length} gün gerçekleşti</b>
        </summary>
        <div className="table-tools">
          <button type="button" className={onlySettled ? 'active' : ''} onClick={() => setOnlySettled(true)}>
            Gerçekleşen günler ({settled.length})</button>
          <button type="button" className={onlySettled ? '' : 'active'} onClick={() => setOnlySettled(false)}>
            {horizonDays} günün tamamı</button>
        </div>
        <div className="table-scroll">
          <table>
            <caption className="sr-live">
              {model.latestDate} tarihli tahminin gün gün değerleri; gerçekleşen kapanış ve sapma oranı.</caption>
            <thead>
              <tr><th>Tarih</th><th>Olası min</th><th>Sinir ağı tahmini</th><th>Olası maks</th><th>Gerçekleşen</th><th>Sapma</th></tr>
            </thead>
            <tbody>{rows.map(row =>
              <tr key={row.day} className={row.real == null ? undefined : 'settled-row'}>
                <td>{shortDate(row.date, true)}</td>
                <td>{money(row.lo)}</td>
                <td>{money(row.v)}</td>
                <td>{money(row.hi)}</td>
                <td>{row.real == null ? <span className="pending">—</span> : <b>{money(row.real)}</b>}</td>
                <td>{row.errorPct == null ? <span className="pending">—</span>
                  : <b className={Math.abs(row.errorPct) <= 0.01 ? 'positive' : 'negative'}>
                      {row.errorPct >= 0 ? '+' : ''}{(row.errorPct * 100).toFixed(2)}%</b>}</td>
              </tr>)}
            </tbody>
          </table>
          {!rows.length && <p className="table-empty">Henüz vadesi dolan gün yok; ilk karşılaştırma yarın eklenecek.</p>}
        </div>
      </details>
    </section>
  );
}

export default ChartSection;
