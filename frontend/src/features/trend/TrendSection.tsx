import { useMemo, useState } from 'react';
import Spinner from '../../components/Spinner';
import { useMinVisible } from '../../app/useMinVisible';
import { aggregate } from '../../domain/chart/aggregate';
import { trendLine } from '../../domain/chart/trend';
import { pct2 } from '../../lib/format';

/* Site genelinde ondalık ayracı virgül; `toFixed` nokta veriyordu. */
const sigma2 = (v: number) =>
  new Intl.NumberFormat('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);
import { featureBy } from '../../content/panel';
import { useDashboard } from '../dashboard/DashboardContext';
import TrendChart from './TrendChart';
import { DEFAULT_RANGE, RANGES, rangeById, type RangeId } from './ranges';

const YON: Record<string, { label: string; tone: string }> = {
  up: { label: 'Yükseliş', tone: 'up' },
  down: { label: 'Düşüş', tone: 'down' },
  flat: { label: 'Yatay', tone: 'flat' },
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
    <section id="feature-trend" className="panel block chart-block trend-block">
      <div className="chart-head">
        <div>
          <h2>{featureBy('feature-trend').title}</h2>
          <p>Seçilen aralıkta fiyatın seyri ve dönemin <b>genel yönü</b>. Trend çizgisi
            noktaları birleştirmez; log fiyat üzerinde regresyonla hesaplanır, yani
            eğim “dönem başına yüzde kaç” olarak okunur.</p>
        </div>
        <div className="chart-tools">
          <div className="tool-group"><span>Zaman aralığı</span>
            <div className="segmented">{RANGES.map(r =>
              <button type="button" key={r.id} className={rangeId === r.id ? 'active' : ''}
                aria-pressed={rangeId === r.id} onClick={() => setRangeId(r.id)}>{r.label}</button>)}
            </div>
          </div>
        </div>
      </div>

      {busy || rows.length < 2
        ? <div className="trend-placeholder">
            {busy ? <Spinner size="lg" label="Fiyat serisi yükleniyor…"/>
              : <span>Bu aralık için yeterli veri yok.</span>}
          </div>
        : <>
            <TrendChart rows={rows} trend={trend} spec={spec}/>

            <div className="market-snapshot trend-snapshot">
              <article className={`snapshot-card trend-card ${yon?.tone ?? 'flat'}`}>
                <span>Dönemin yönü</span>
                <strong>{yon?.label ?? '—'}</strong>
                <small>{spec.label.toLowerCase()} seride son {rows.length} nokta</small>
              </article>
              <article className="snapshot-card">
                <span>Trend eğimi</span>
                <strong>{trend ? pct2(trend.slopePct) : '—'}</strong>
                <small>{spec.unit} başına, regresyon eğimi</small>
              </article>
              <article className="snapshot-card">
                <span>Gerçekleşen değişim</span>
                <strong>{gerceklesen === null ? '—' : pct2(gerceklesen)}</strong>
                <small>dönem başı ve sonu kapanışı arasındaki fark</small>
              </article>
              <article className="snapshot-card">
                <span>Kanalda konum</span>
                <strong>{trend
                  ? `${trend.lastZ >= 0 ? '+' : ''}${sigma2(trend.lastZ)}σ` : '—'}</strong>
                <small>{trend ? kanalMetni(trend.lastZ) : '—'}</small>
              </article>
              <article className="snapshot-card">
                <span>Uyum</span>
                <strong>{trend ? `%${Math.round(trend.r2 * 100)}` : '—'}</strong>
                <small>{trend
                  ? `${uyumMetni(trend.r2)} · kanal ±${pct2(trend.sigma).replace('%', '')}%`
                  : '—'}</small>
              </article>
            </div>

            <div className="chart-legend">
              <span><i className={spec.candles ? 'history-key' : 'history-key'}/>
                {spec.candles ? 'Günlük mumlar (gövde: önceki kapanış → kapanış)' : 'Dönem kapanışları'}</span>
              <span><i className={`trend-key ${trend?.direction ?? 'flat'}`}/>Genel yön (regresyon)</span>
              {trend && trend.sigma > 0 &&
                <span><i className="trend-key band"/>Kanal: trend ±1σ ve ±2σ</span>}
            </div>

            <p className="trend-note">
              Trend çizgisi geçmişin özetidir, geleceğin tahmini değildir. Kanal,
              fiyatın trend etrafındaki <b>tipik sapmasını</b> gösterir: dar kanal
              seyrin trendi yakından izlediği, geniş kanal dağınık olduğu anlamına
              gelir. Kanalın dışına çıkmak bir dönüş sinyali değildir — bu sitede
              böyle bir sinyalin işe yaradığı <b>ölçülemedi</b>. Modelin ölçülmüş
              tahmini yukarıdaki grafik kartında.
            </p>
          </>}
    </section>
  );
}

export default TrendSection;
