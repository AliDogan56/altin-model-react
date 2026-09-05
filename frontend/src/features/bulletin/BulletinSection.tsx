import Collapsible from '../../components/Collapsible';
import DataTimestamp from '../../components/ui/DataTimestamp';
import { PANEL_FEATURES } from '../../content/panel';
import { pct } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

function BulletinSection({ focus }: { focus?: string }) {
  const { news, live, featuresDate, status } = useDashboard();
  const drivers = [
    { label: 'Reel faiz', value: live.real_yield_change_5d, format: (v: number) => `${v >= 0 ? '+' : ''}${v.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} puan`, unit: '10 yıllık · 5 günlük değişim' },
    { label: 'Dolar endeksi', value: live.dollar_return_5d, format: pct, unit: 'Geniş dolar · 5 günlük getiri' },
    { label: 'VIX', value: live.vix_change_5d, format: (v: number) => `${v >= 0 ? '+' : ''}${v.toLocaleString('tr-TR', { maximumFractionDigits: 2 })}`, unit: '5 günlük değişim' },
  ];
  return <Collapsible id="bulletin" anchor="feature-bulten" openByDefault={focus === PANEL_FEATURES.find(f => f.anchor === 'feature-bulten')?.slug}
    title="Makro etkenler ve haber akışı" hint="Model girdilerini, güncel ekonomi gündemiyle birlikte okuyun." summary={news.length ? `${news.length} haber` : undefined}>
    <section className="macro-news">
      <div className="macro-drivers">
        {drivers.map(driver => <div key={driver.label}><span>{driver.label}</span><strong>{driver.value != null ? driver.format(driver.value) : '—'}</strong><small>{driver.unit}</small></div>)}
      </div>
      <div className="macro-context"><DataTimestamp time={featuresDate} staleAfterMs={7 * 86400000}/><p>Makro seriler yayın takvimine göre gecikmeli gelir. Sıfır değişim, yeni gözlem yayımlanmamış olmasından da kaynaklanabilir.</p></div>
      <div className="news-list" aria-busy={!!status.busy}>
        {news.length ? news.map(item => <a key={item.url || item.title} href={item.url} target="_blank" rel="noreferrer"><span className="news-source">{item.source || 'Ekonomi gündemi'}</span><strong>{item.title}</strong><span aria-hidden="true">↗</span></a>)
          : <p className="data-empty">{status.busy ? 'Haberler yükleniyor…' : 'Haber kaynağına şu anda ulaşılamıyor. Piyasa verileri diğer bölümlerde kullanılabilir.'}</p>}
      </div>
      <p className="analysis-footnote">Başlıklar otomatik haber akışından gelir; model tarafından doğrulanmış bir pozitif/negatif etki skoru içermez.</p>
    </section>
  </Collapsible>;
}
export default BulletinSection;
