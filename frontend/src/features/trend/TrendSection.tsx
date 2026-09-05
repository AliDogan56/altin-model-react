import { useMemo, useState } from 'react';
import { useMinVisible } from '../../app/useMinVisible';
import SegmentedControl from '../../components/ui/SegmentedControl';
import { aggregate } from '../../domain/chart/aggregate';
import { trendLine } from '../../domain/chart/trend';
import { pct2 } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';
import TrendChart from './TrendChart';
import { DEFAULT_RANGE, RANGES, rangeById, type RangeId } from './ranges';

/* Site genelinde ondalık ayracı virgül; `toFixed` nokta veriyordu. */
const sigma2 = (v: number) =>
  new Intl.NumberFormat('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);

const YON: Record<string, { label: string; tone: string }> = {
  up: { label: '↑ Yükseliş eğilimi', tone: 'up' },
  down: { label: '↓ Düşüş eğilimi', tone: 'down' },
  flat: { label: '→ Yatay', tone: 'flat' },
};

const RANGE_SHORT: Record<RangeId, string> = {
  gunluk: '1G', haftalik: '1H', aylik: '1A', ceyreklik: '3A', yarim: '6A',
};

/** Fiyatın kanaldaki yerini sade dile çevirir. */
const kanalMetni = (z: number) =>
  z > 2 ? 'kanalın belirgin üstünde' : z > 1 ? 'trendin üstünde'
    : z < -2 ? 'kanalın belirgin altında' : z < -1 ? 'trendin altında'
      : 'trend çizgisine yakın';

/** Uyum iyiliğini sade dile çevirir; r² tek başına okura bir şey söylemiyor. */
const uyumMetni = (r2: number) =>
  r2 >= 0.75 ? 'seyir trendi yakından izliyor'
    : r2 >= 0.4 ? 'seyir trend etrafında dalgalı'
      : 'dağınık seyir, genel yön zayıf';

/**
 * Trend grafiği kartı. Veri yeni bir uçtan gelmez: panelin zaten çektiği günlük
 * OHLC serisi seçilen aralığa göre toplanır. Aralık değişince seri, ölçek ve
 * trend yeniden hesaplanır.
 */
function TrendSection() {
  const { candles } = useDashboard();
  const [rangeId, setRangeId] = useState<RangeId>(DEFAULT_RANGE);
  const spec = rangeById(rangeId);
  const busy = useMinVisible(candles.length === 0);

  const rows = useMemo(
    () => aggregate(candles, spec.bucket).slice(-spec.bars),
    [candles, spec.bucket, spec.bars]);
  const trend = useMemo(() => trendLine(rows.map(r => r.c)), [rows]);
  /* Gerçekleşen değişim ile trend çizgisinin uçları farklıdır ve fark büyük
     olabilir (ölçüldü: 60 aylık seride ham %148, trend uçları %203). Kullanıcı
     karttaki sayıyı fiyat değişimi sanmasın diye **gerçekleşeni** gösteriyoruz;
     trendin kendi uçları grafikte zaten çizili. */
  const gerceklesen = rows.length > 1 && rows[0].c > 0 ? rows[rows.length - 1].c / rows[0].c - 1 : null;

  const yon = trend ? YON[trend.direction] : null;

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
                <span aria-hidden="true">{RANGE_SHORT[r.id]}</span>
                <span className="sr-live">{r.label}</span></> }))}
              onChange={setRangeId}/>
          </div>
        </div>
      </div>

      {busy || rows.length < 2
        ? <div className="trend-placeholder" role="status">
            {busy ? <><div className="trend-skeleton" aria-hidden="true"/><span>Fiyat serisi yükleniyor…</span></>
              : <span>Bu aralık için yeterli veri yok.</span>}
          </div>
        : <>
            <div className="trend-context">
              <strong className={yon?.tone ?? 'flat'}>{yon?.label ?? 'Yön hesaplanamadı'}</strong>
              <span>{spec.label} kapanışlar · {rows.length} gözlem</span>
            </div>

            <TrendChart rows={rows} trend={trend} spec={spec}/>

            <dl className="trend-metrics">
              <div><dt>Gerçekleşen değişim</dt><dd>{gerceklesen === null ? '—' : pct2(gerceklesen)}
                <small>ilk ve son kapanış arası</small></dd></div>
              <div><dt>Trend eğimi</dt><dd>{trend ? pct2(trend.slopePct) : '—'}
                <small>{spec.unit} başına regresyon eğimi</small></dd></div>
              <div><dt>Kanalda konum</dt><dd>{trend
                ? `${trend.lastZ >= 0 ? '+' : ''}${sigma2(trend.lastZ)}σ` : '—'}
                <small>{trend ? kanalMetni(trend.lastZ) : '—'}</small></dd></div>
              <div><dt>Trend uyumu · R²</dt><dd>{trend ? `%${Math.round(trend.r2 * 100)}` : '—'}
                <small>{trend ? uyumMetni(trend.r2) : '—'}</small></dd></div>
              <div><dt>Kanaldaki sapma · σ</dt><dd>{trend ? pct2(trend.sigma) : '—'}
                <small>log fiyat artıklarının sapması</small></dd></div>
            </dl>

            <div className="chart-legend">
              <span><i className="history-key"/>{spec.candles ? 'Günlük mumlar' : 'Dönem kapanışları'}</span>
              <span><i className={`trend-key ${trend?.direction ?? 'flat'}`}/>Genel yön (regresyon)</span>
              {trend && trend.sigma > 0 &&
                <span><i className="trend-key band"/>Kanal: trend ±1σ ve ±2σ</span>}
            </div>

            <details className="chart-help">
              <summary>Periyot ve trend hesabı hakkında</summary>
              <div className="chart-help-content">
                <p>1G / 1H / 1A / 3A / 6A, her veri noktasının toplama periyodudur;
                  grafiğin toplam süresi değildir. Seçili {spec.label.toLowerCase()} seride
                  son {rows.length} kapanış gösteriliyor. Eğim, log fiyat regresyonundan
                  hesaplanan {spec.unit} başına değişimdir.</p>
                {spec.candles && <p>Mum gövdesi önceki kapanıştan günlük kapanışa uzanır;
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
