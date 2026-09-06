import { useState } from 'react';
import Spinner from '../../components/Spinner';
import SegmentedControl from '../../components/ui/SegmentedControl';
import { FRAME, OUTSIDE, PIVOT_PERIOD, SERVICE_UNREACHABLE, STATUS_TEXT, type BlockStatus } from '../../content/technical';
import { resolveHorizon } from '../../domain/model/horizon';
import { money } from '../../lib/format';
import type { PivotPeriod } from '../../services/api/technical';
import { useDashboard } from '../dashboard/DashboardContext';
import ForecastChart from './ForecastChart';

const RANGES: [number, string][] = [[30, '1 Ay'], [90, '3 Ay'], [180, '6 Ay'], [260, '1 Yıl']];
/** "Önceki tam …" cümlesi için dönem adının tamlayan hâli. */
const PERIOD_OF: Record<PivotPeriod, string> = { DAILY: 'günün', WEEKLY: 'haftanın', MONTHLY: 'ayın' };

const isKnownStatus = (status: string | undefined): status is BlockStatus =>
  status != null && status in STATUS_TEXT;

/**
 * Veri gelmeden grafiğin ne yazacağı. Sunucunun günlük blok durumu biliniyorsa
 * onun cümlesi; servis ulaşılamazsa "alınamadı"; aksi hâlde bekleniyor.
 * Eskiden bu boşluk pakete gömülü yedek seriyle doluyordu; o seri kalktı ve
 * boşluk 0 $'da düz bir çizgi olarak görünmeye başladı — sayı uydurmak yerine durum yazılır.
 */
const waitingText = (dailyStatus: string | undefined, technicalStatus: string): string => {
  if (isKnownStatus(dailyStatus) && STATUS_TEXT[dailyStatus]) return STATUS_TEXT[dailyStatus]!;
  if (technicalStatus === 'fallback') return STATUS_TEXT.NO_DATA!;
  return 'Veri bekleniyor';
};

/**
 * En yakın seviye yokken yazılacak cümle: sunucu "tüm seviyelerin dışında"
 * dediyse onun sözü, merdiven hiç gelmediyse pivot bloğunun durumu. Konum
 * burada çıkarsanmaz — sunucu test edilen seviyeyi atlayıp bir sonrakini
 * `NEAREST_*` yapar; sıraya bakarak seçmek o kararı eziyordu.
 */
const noLevelText = (ladderOutside: string | null | undefined, pivotStatus: string | undefined, technicalStatus: string): string => {
  if (ladderOutside && ladderOutside in OUTSIDE) return OUTSIDE[ladderOutside as keyof typeof OUTSIDE];
  if (isKnownStatus(pivotStatus) && STATUS_TEXT[pivotStatus]) return STATUS_TEXT[pivotStatus]!;
  return technicalStatus === 'fallback' ? SERVICE_UNREACHABLE : 'Veri bekleniyor';
};

function ChartSection() {
  const {
    history, candles, spot, reference, technical, technicalStatus, rangeDays, setRangeDays, horizonDays,
    forecast, modelStatus, confident, pivotLadder, pivotPeriod, levels, hasForecast,
  } = useDashboard();
  /* Seviye katmanının fiyatı teknik paketin referansı; Harem kotasyonu merdivene girmez. */
  const price = reference?.value ?? null;
  const { index } = resolveHorizon(forecast.horizons, horizonDays);
  const [candleMode, setCandleMode] = useState(false);
  const hasCandles = candles.length > 0;
  const available = (modelStatus === 'live' || (modelStatus === 'loading' && hasForecast))
    && confident[index] !== false;
  const items = pivotLadder?.items ?? [];
  /* Sunucunun rolü: test edilen seviye hedef değildir, `NEAREST_*` bir sonrakidir. */
  const support = items.find(i => i.role === 'NEAREST_DOWN');
  const resistance = items.find(i => i.role === 'NEAREST_UP');
  const zones = levels?.zones ?? [];
  /* Dar ekranda çizilecek bölgeler sunucunun seçimi: en yakın iki taraf, test edilenler, sonrakiler. */
  const focusZoneIds = levels
    ? [levels.nearestSupport, levels.nearestResistance, ...levels.testing, levels.nextSupport, levels.nextResistance]
        .filter((id): id is string => id != null)
    : [];
  const periodLabel = PIVOT_PERIOD[pivotPeriod];
  const waiting = history.length === 0 || !spot.live || price == null || !reference;
  const noLevel = noLevelText(pivotLadder?.outside, technical?.status.pivots, technicalStatus);

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

      {waiting
        ? <div className="chart-wrap forecast-chart">
            <div className="chart-canvas">
              <div className="loading-row" role="status">
                {technicalStatus === 'loading'
                  ? <Spinner size="lg" label={waitingText(technical?.status.daily, technicalStatus)}/>
                  : <span>{waitingText(technical?.status.daily, technicalStatus)}</span>}
              </div>
            </div>
          </div>
        : <ForecastChart
            forecast={forecast} available={available}
            history={history} candles={candles} candleMode={candleMode}
            rangeDays={rangeDays} horizonDays={horizonDays}
            levels={items} levelPeriod={periodLabel} zones={zones} focusZoneIds={focusZoneIds}
            reference={{ value: price, frame: reference.frame }} describedById="destek-direnc-aciklama"/>}

      {!available && modelStatus !== 'loading' && <p className="chart-status" role="status">
        {modelStatus === 'live'
          ? 'Model bu vadede yön bildirmiyor. Gerçekleşen fiyatları inceleyebilirsiniz.'
          : 'Model servisi çevrimdışı. Gerçekleşen fiyatlar gösteriliyor.'}
      </p>}

      <details className="chart-help">
        <summary>Grafiği ve seviyeleri nasıl okumalı?</summary>
        <div id="destek-direnc-aciklama" className="chart-help-content">
          <p>Sol taraf gerçekleşen günlük kapanışları, sağ taraf seçili vadedeki model
            beklentisini gösterir. Katman düğmeleriyle fiyat, referans, model, belirsizlik
            bandı, pivot seviyeleri ve test edilmiş bölgeleri bağımsız olarak açıp kapatabilirsiniz.</p>
          <p>Seviyeler <b>{periodLabel.toLowerCase()} pivot</b> hesabından gelir; önceki tam
            {' '}{PERIOD_OF[pivotPeriod]} en yüksek, en düşük ve kapanış
            fiyatı kullanılır. Destek / direnç paneliyle aynı kaynaktır; dönem ve yöntem
            seçimini o panelden değiştirebilirsiniz.</p>
          <dl className="chart-level-summary">
            <div><dt>Referans fiyat</dt><dd>{price != null && reference
              ? `${money(price)} · ${FRAME[reference.frame]}` : waitingText(technical?.status.daily, technicalStatus)}</dd></div>
            <div><dt>En yakın destek</dt><dd>{support
              ? `${support.name} · ${money(support.value)}` : noLevel}</dd></div>
            <div><dt>En yakın direnç</dt><dd>{resistance
              ? `${resistance.name} · ${money(resistance.value)}` : noLevel}</dd></div>
          </dl>
          <p><b>P</b> pivot noktasıdır. Destek ve dirençler birer referans bölgedir;
            fiyatın bu bölgelerden dönmesi veya içinde kalması garanti değildir.
            <b> Bölgeler</b> katmanı fiyatın geçmişte fiilen döndüğü ya da kırdığı aralıkları
            gösterir; koyuluk o bölgenin kaç kez test edildiğini anlatır, bir güç iddiası değildir.</p>
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
