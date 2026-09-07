import Collapsible from '../../components/Collapsible';
import SegmentedControl from '../../components/ui/SegmentedControl';
import { PANEL_FEATURES } from '../../content/panel';
import { useDashboard } from '../dashboard/DashboardContext';
import PriceLadder from './PriceLadder';

function PivotSection({ focus }: { focus?: string }) {
  const { pivotPeriod, setPivotPeriod, pivotMethod, setPivotMethod, pivotLadder } = useDashboard();
  return <Collapsible id="pivot" anchor="feature-pivot"
    openByDefault={focus === PANEL_FEATURES.find(f => f.anchor === 'feature-pivot')?.slug}
    title="Destek ve direnç seviyeleri" hint="Canlı fiyatın, tamamlanmış dönemin pivot seviyeleri arasındaki konumu."
    summary={pivotLadder?.nearestUp ? `İlk direnç · ${pivotLadder.nearestUp}` : undefined}>
    <section className="panel block pivot-block" aria-label="Pivot merdiveni">
      <div className="pivot-head"><div className="pivot-tools">
        <SegmentedControl label="Pivot dönemi" value={pivotPeriod} onChange={setPivotPeriod} options={[{ value: 'weekly', label: 'Haftalık' }, { value: 'monthly', label: 'Aylık' }]}/>
        <SegmentedControl label="Pivot yöntemi" value={pivotMethod} onChange={setPivotMethod} options={[{ value: 'classic', label: 'Klasik' }, { value: 'fib', label: 'Fibonacci' }]}/>
      </div></div>
      <PriceLadder ladder={pivotLadder}/>
      {pivotLadder && !pivotLadder.nearestUp && <p className="pivot-alert">Fiyat tüm seviyelerin üzerinde; bu dönemde yukarıda kalan bir direnç yok.</p>}
      {pivotLadder && !pivotLadder.nearestDown && <p className="pivot-alert">Fiyat tüm seviyelerin altında; bu dönemde aşağıda kalan bir destek yok.</p>}
      <p className="pivot-note">Önceki tamamlanmış {pivotPeriod === 'monthly' ? 'ayın' : 'haftanın'} yüksek, düşük ve kapanışından hesaplanır{pivotLadder ? ` (dönem: ${pivotLadder.id})` : ''}.
        Ana grafik aynı seviyeleri kullanır. Çizgiler kesin sınırlar değil, izlenecek referans bölgeleridir. <a href="/rehber/altin-destek-direnc">Nasıl okunur?</a></p>
    </section>
  </Collapsible>;
}
export default PivotSection;
