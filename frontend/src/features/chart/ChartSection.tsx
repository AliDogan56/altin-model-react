import { useState } from 'react';
import SegmentedControl from '../../components/ui/SegmentedControl';
import { money } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';
import ForecastChart from './ForecastChart';

const RANGES: [number, string][] = [[30, '1 Ay'], [90, '3 Ay'], [180, '6 Ay'], [260, '1 Yıl']];

function ChartSection() {
  const {
    history, candles, spot, harem, rangeDays, setRangeDays, horizonDays,
    showOrigin, setShowOrigin, forecast, originForecast, modelStatus, confident,
    pivotLadder, pivotPeriod, hasForecast,
  } = useDashboard();
  const price = harem.satis || spot.price;
  const index = Math.max(0, forecast.horizons.indexOf(horizonDays));
  const [candleMode, setCandleMode] = useState(false);
  const hasCandles = candles.length > 0;
  const available = (modelStatus === 'live' || (modelStatus === 'loading' && hasForecast))
    && confident[index] !== false;
  const items = pivotLadder?.items ?? [];
  const resistance = items.filter(i => i.above).at(-1);
  const support = items.find(i => !i.above);
  const periodLabel = pivotPeriod === 'monthly' ? 'Aylık' : 'Haftalık';

  return (
    <section id="feature-grafik" className="panel block chart-block terminal-chart">
      <div className="chart-head">
        <div>
          <h2>Fiyat ve model projeksiyonu</h2>
          <p>XAU/USD · günlük kapanışlar · {horizonDays} günlük model görünümü</p>
        </div>
        {modelStatus === 'loading' && <span className="chart-update" role="status">
          {hasForecast ? 'Model güncelleniyor' : 'Model bekleniyor'}
        </span>}
      </div>

      <div className="chart-tools">
        <div className="tool-group">
          <span>Geçmiş</span>
          <SegmentedControl label="Grafikte gösterilen geçmiş" value={rangeDays}
            options={RANGES.map(([value, label]) => ({ value, label }))} onChange={setRangeDays}/>
        </div>
        <div className="tool-group">
          <span>Görünüm</span>
          <SegmentedControl label="Grafik görünümü" value={candleMode ? 'candle' : 'line'}
            options={[{ value: 'line', label: 'Çizgi' },
              { value: 'candle', label: 'Mum', disabled: !hasCandles }]}
            onChange={value => setCandleMode(value === 'candle')}/>
        </div>
      </div>

      <ForecastChart
        forecast={forecast} originForecast={originForecast} available={available}
        history={history} candles={candles} candleMode={candleMode}
        rangeDays={rangeDays} horizonDays={horizonDays}
        showOrigin={showOrigin} onToggleOrigin={() => setShowOrigin(v => !v)}
        levels={items} levelPeriod={periodLabel}
        spot={{ ...spot, price, live: harem.live }} describedById="destek-direnc-aciklama"/>

      {!available && modelStatus !== 'loading' && <p className="chart-status" role="status">
        {modelStatus === 'live'
          ? 'Model bu vadede yön bildirmiyor. Gerçekleşen fiyatları inceleyebilirsiniz.'
          : 'Model servisi çevrimdışı. Gerçekleşen fiyatlar gösteriliyor.'}
      </p>}

      <details className="chart-help">
        <summary>Grafiği ve seviyeleri nasıl okumalı?</summary>
        <div id="destek-direnc-aciklama" className="chart-help-content">
          <p>Sol taraf gerçekleşen günlük kapanışları, sağ taraf seçili vadedeki model
            beklentisini gösterir. Katman düğmeleriyle fiyat, model, belirsizlik bandı ve
            destek / direnç bölgelerini bağımsız olarak açıp kapatabilirsiniz.</p>
          <p>Seviyeler <b>{periodLabel.toLowerCase()} pivot</b> hesabından gelir; önceki tam
            {pivotPeriod === 'monthly' ? ' ayın' : ' haftanın'} en yüksek, en düşük ve kapanış
            fiyatı kullanılır. Destek / direnç paneliyle aynı kaynaktır; dönem ve yöntem
            seçimini o panelden değiştirebilirsiniz.</p>
          <dl className="chart-level-summary">
            <div><dt>En yakın destek</dt><dd>{support
              ? `${support.name} · ${money(support.value)}` : 'Gösterilen seviyelerin altında'}</dd></div>
            <div><dt>En yakın direnç</dt><dd>{resistance
              ? `${resistance.name} · ${money(resistance.value)}` : 'Gösterilen seviyelerin üzerinde'}</dd></div>
          </dl>
          <p><b>P</b> pivot noktasıdır. Destek ve dirençler birer referans bölgedir;
            fiyatın bu bölgelerden dönmesi veya içinde kalması garanti değildir.</p>
          {candleMode && hasCandles && <p><b>Mum görünümü:</b> fitil günün ölçülmüş en yüksek
            ve en düşük fiyatını gösterir. Kaynak açılış vermediği için gövde önceki kapanıştan
            bugünkü kapanışa uzanır; yeşil yükseliş, kırmızı düşüştür.</p>}
          <p>Grafikte ok tuşlarıyla gün gün, Shift + ok ile yedi gün ilerleyebilirsiniz.
            Home / End ilk ve son güne gider; Escape seçimi kapatır. Dokunmatik ekranda
            parmağınızı gezdirerek gün seçin, iki parmakla yakınlaştırıp kaydırın.</p>
        </div>
      </details>
    </section>
  );
}

export default ChartSection;
