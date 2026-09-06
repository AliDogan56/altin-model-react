import { useState } from 'react';
import { useMinVisible } from '../../app/useMinVisible';
import SegmentedControl from '../../components/ui/SegmentedControl';
import { FRAME, STATUS_TEXT, type BlockStatus } from '../../content/technical';
import { CHANNEL_STATE, DIRECTION, FIT_STATE, TIMEFRAME, type TrendDirection } from '../../content/trend';
import { pct2 } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';
import TrendChart from './TrendChart';
import { DEFAULT_RANGE, RANGES, type RangeId } from './ranges';

/* Site genelinde ondalık ayracı virgül; `toFixed` nokta veriyordu. */
const sigma2 = (v: number) =>
  new Intl.NumberFormat('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);

/** Yön oku yalnız süs; metin ve ton sözlükten (`DIRECTION`) gelir. */
const ARROW: Record<TrendDirection, string> = { UP: '↑', DOWN: '↓', FLAT: '→' };

/**
 * Sunucu durum anahtarı sözlükte yoksa (ör. `MISSING`, gelecekte eklenen bir
 * değer) kart boş kalmasın; genel bir "alınamadı" cümlesine düşer.
 */
const statusText = (status: string): string =>
  STATUS_TEXT[status as BlockStatus] ?? 'Trend verisi alınamadı';

/**
 * Trend grafiği kartı. Hesabın tamamı sunucuda (`/v1/market/xau/technical` →
 * `trend.ranges[id]`): kovalama, log-OLS eğimi, kanal bantları, gerçekleşen
 * değişim ve durum etiketleri oradan gelir. Kart yalnız seçili aralığı gösterir;
 * aralık değişince yeni istek atılmaz, yanıtın başka bir anahtarı okunur.
 */
function TrendSection() {
  const { technical, technicalStatus, trend } = useDashboard();
  const [rangeId, setRangeId] = useState<RangeId>(DEFAULT_RANGE);
  const busy = useMinVisible(technical === null && technicalStatus === 'loading');

  const range = trend?.ranges[rangeId] ?? null;
  const fit = range?.fit ?? null;
  const rows = range?.rows ?? [];
  const unit = range ? TIMEFRAME[range.timeframe] : null;
  const direction = fit ? DIRECTION[fit.direction] : null;
  const channel = range?.channelState ? CHANNEL_STATE[range.channelState] : null;
  const fitState = range?.fitState ? FIT_STATE[range.fitState] : null;

  /* Boş durum tek yerden karar verilir: yükleniyor → iskelet; teknik paket yok
     ya da trend bloğu yok → blok durumu; aralık `OK` değil → aralık durumu. */
  const placeholder = busy ? null
    : technical === null ? 'Teknik analiz alınamadı'
      : trend === null ? statusText(technical.status.trend)
        : range === null ? statusText('MISSING')
          : range.status !== 'OK' ? statusText(range.status)
            : rows.length < 2 ? statusText('INSUFFICIENT_DATA')
              : null;

  return (
    <section id="feature-trend" className="panel block chart-block trend-block terminal-trend">
      <div className="chart-head">
        <div>
          <h2>Trend ve fiyat kanalı</h2>
          <p>Geçmiş fiyatların genel yönü ve trend etrafındaki dağılımı.</p>
        </div>
        <div className="chart-tools">
          <div className="tool-group"><span>Veri periyodu</span>
            <SegmentedControl label="Trend verilerinin toplama periyodu" value={rangeId}
              options={RANGES.map(r => ({ value: r.id, label: <>
                <span aria-hidden="true">{r.short}</span>
                <span className="sr-live">{r.label}</span></> }))}
              onChange={setRangeId}/>
          </div>
        </div>
      </div>

      {busy || placeholder || !range
        ? <div className="trend-placeholder" role="status">
            {busy ? <><div className="trend-skeleton" aria-hidden="true"/><span>Fiyat serisi yükleniyor…</span></>
              : <span>{placeholder}</span>}
          </div>
        : <>
            <div className="trend-context">
              <strong className={direction?.tone ?? 'flat'}>
                {direction ? `${ARROW[fit!.direction]} ${direction.label} eğilimi` : 'Yön hesaplanamadı'}
              </strong>
              {/* Seri günlük kapanışlardan kovalanır; referans çerçevesi bu yüzden
                  her zaman günlük kapanış — gün içi son fiyat trend serisine girmez. */}
              <span>{RANGES.find(r => r.id === rangeId)?.label} kapanışlar · {rows.length} gözlem
                {range.lastBucketForming && ' · son dönem oluşuyor'} · {FRAME.daily_close}</span>
            </div>

            <TrendChart rows={rows} fit={fit} candles={range.candles} timeframe={range.timeframe}
              label={RANGES.find(r => r.id === rangeId)?.label ?? rangeId}/>

            <dl className="trend-metrics">
              {/* Gerçekleşen değişim ile trend çizgisinin uçları farklıdır ve fark
                  büyük olabilir (ölçüldü: 60 aylık seride ham %148, trend uçları
                  %203). Kart **gerçekleşeni** gösterir (`realizedPct`); trendin
                  uçları grafikte zaten çizili. */}
              <div><dt>Gerçekleşen değişim</dt><dd>{range.realizedPct === null ? '—' : pct2(range.realizedPct)}
                <small>ilk ve son kapanış arası</small></dd></div>
              <div><dt>Trend eğimi</dt><dd>{fit ? pct2(fit.slopePct) : '—'}
                <small>{unit} başına regresyon eğimi</small></dd></div>
              <div><dt>Kanalda konum</dt><dd>{fit
                ? `${fit.lastZ >= 0 ? '+' : ''}${sigma2(fit.lastZ)}σ` : '—'}
                <small>{channel?.note ?? '—'}</small></dd></div>
              <div><dt>Trend uyumu · R²</dt><dd>{fit ? `%${Math.round(fit.r2 * 100)}` : '—'}
                <small>{fitState?.note ?? '—'}</small></dd></div>
              <div><dt>Kanaldaki sapma · σ</dt><dd>{fit ? pct2(fit.sigma) : '—'}
                <small>log fiyat artıklarının sapması</small></dd></div>
            </dl>

            <div className="chart-legend">
              <span><i className="history-key"/>{range.candles ? 'Günlük mumlar' : 'Dönem kapanışları'}</span>
              <span><i className={`trend-key ${direction?.tone ?? 'flat'}`}/>Genel yön (regresyon)</span>
              {fit && fit.sigma > 0 &&
                <span><i className="trend-key band"/>Kanal: trend ±1σ ve ±2σ</span>}
              {range.lastBucketForming &&
                <span><i className="trend-key forming"/>Oluşan dönem (kapanmadı)</span>}
            </div>

            <details className="chart-help">
              <summary>Periyot ve trend hesabı hakkında</summary>
              <div className="chart-help-content">
                <p>1G / 1H / 1A / 3A / 6A, her veri noktasının toplama periyodudur;
                  grafiğin toplam süresi değildir. Seçili seride son {rows.length} kapanış
                  gösteriliyor. Eğim, log fiyat regresyonundan hesaplanan {unit} başına
                  değişimdir; hesap sunucuda yapılır, kart yalnız gösterir.</p>
                {range.candles && <p>Mum gövdesi önceki kapanıştan günlük kapanışa uzanır;
                  fitil günün en yüksek ve en düşük fiyatını gösterir. Kaynak açılış fiyatı vermez.</p>}
                <p>Trend çizgisi geçmişin özetidir, geleceğin tahmini değildir. Kanal,
                  fiyatın trend etrafındaki <b>tipik sapmasını</b> gösterir: dar kanal
                  seyrin trendi yakından izlediği, geniş kanal dağınık olduğu anlamına
                  gelir. Kanalın dışına çıkmak bir dönüş sinyali değildir — bu sitede
                  böyle bir sinyalin işe yaradığı <b>ölçülemedi</b>. Modelin ölçülmüş
                  tahmini model görünümünde yer alır.
                </p>
              </div>
            </details>
          </>}
    </section>
  );
}

export default TrendSection;
