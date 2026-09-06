import Collapsible from '../../components/Collapsible';
import SegmentedControl from '../../components/ui/SegmentedControl';
import { PANEL_FEATURES } from '../../content/panel';
import { COMPLETION, NOTE_TEXT, OUTSIDE, PIVOT_METHOD, PIVOT_PERIOD, type TechnicalNote } from '../../content/technical';
import { money } from '../../lib/format';
import { PIVOT_METHODS, PIVOT_PERIODS } from '../../services/api/technical';
import { useDashboard } from '../dashboard/DashboardContext';
import PriceLadder, { statusText } from './PriceLadder';

const noteText = (note: string | null | undefined): string | null =>
  note && note in NOTE_TEXT ? NOTE_TEXT[note as TechnicalNote] : null;

/**
 * Pivot kartı: dönem/yöntem seçimi sunucuya gider, merdiven ve dönem bilgisi
 * sunucudan gelir. Dönemin tamamlanma kuralı, "tüm seviyelerin dışında"
 * kararı ve en yakın seviye seçimi burada **yeniden hesaplanmaz**; kart
 * yalnız `headline` alanlarını sözlükten geçirip yazar.
 */
function PivotSection({ focus }: { focus?: string }) {
  const { pivotPeriod, setPivotPeriod, pivotMethod, setPivotMethod, pivotLadder, pivotHeadline, reference, technical } = useDashboard();
  const nearestUp = pivotLadder?.items.find(item => item.role === 'NEAREST_UP') ?? null;
  const blockStatus = statusText(technical?.status.pivots);
  const periodStatus = statusText(pivotHeadline?.status);
  const liveQuoteNote = noteText(reference?.note);
  return <Collapsible id="pivot" anchor="feature-pivot"
    openByDefault={focus === PANEL_FEATURES.find(f => f.anchor === 'feature-pivot')?.slug}
    title="Destek ve direnç seviyeleri" hint="Referans fiyatın, tamamlanmış dönemin pivot seviyeleri arasındaki konumu."
    summary={nearestUp ? `İlk direnç · ${nearestUp.name} ${money(nearestUp.value)}` : undefined}>
    <section className="panel block pivot-block" aria-label="Pivot merdiveni">
      <div className="pivot-head"><div className="pivot-tools">
        <SegmentedControl label="Pivot dönemi" value={pivotPeriod} onChange={setPivotPeriod}
          options={PIVOT_PERIODS.map(value => ({ value, label: PIVOT_PERIOD[value] }))}/>
        <SegmentedControl label="Pivot yöntemi" value={pivotMethod} onChange={setPivotMethod}
          options={PIVOT_METHODS.map(value => ({ value, label: PIVOT_METHOD[value] }))}/>
      </div></div>
      {blockStatus && <p className="pivot-alert">{blockStatus}</p>}
      <PriceLadder ladder={pivotLadder}/>
      {pivotLadder?.outside && <p className="pivot-alert">{OUTSIDE[pivotLadder.outside]}; bu dönemde {pivotLadder.outside === 'ABOVE_ALL' ? 'yukarıda kalan bir direnç' : 'aşağıda kalan bir destek'} yok.</p>}
      {periodStatus && <p className="pivot-alert">{periodStatus}{pivotHeadline?.missingBarFor ? ` (eksik mum: ${pivotHeadline.missingBarFor})` : ''}.</p>}
      {pivotHeadline && <dl className="pivot-period">
        <div><dt>Dönem</dt><dd>{PIVOT_PERIOD[pivotHeadline.period]} · {pivotHeadline.periodId}{pivotHeadline.bars ? ` · ${pivotHeadline.bars} mum` : ''}</dd></div>
        <div><dt>Yüksek</dt><dd>{pivotHeadline.high !== null ? money(pivotHeadline.high) : '—'}</dd></div>
        <div><dt>Düşük</dt><dd>{pivotHeadline.low !== null ? money(pivotHeadline.low) : '—'}</dd></div>
        <div><dt>Kapanış</dt><dd>{pivotHeadline.close !== null ? money(pivotHeadline.close) : '—'}</dd></div>
        <div className="wide"><dt>Tamamlanma</dt><dd>{COMPLETION[pivotHeadline.completion]}</dd></div>
      </dl>}
      <p className="pivot-note">
        {pivotHeadline ? `${PIVOT_METHOD[pivotHeadline.method]} seviyeler önceki tamamlanmış dönemin yüksek, düşük ve kapanışından hesaplanır.` : 'Seviyeler önceki tamamlanmış dönemin yüksek, düşük ve kapanışından hesaplanır.'}
        {pivotLadder ? ` Referansın ±${money(pivotLadder.marginUsd)} içindeki seviye "test ediliyor" sayılır ve hedef alınmaz.` : ''}
        {liveQuoteNote ? ` ${liveQuoteNote}.` : ''}
        {' '}Ana grafik aynı seviyeleri kullanır. Çizgiler kesin sınırlar değil, izlenecek referans bölgeleridir. <a href="/rehber/altin-destek-direnc">Nasıl okunur?</a></p>
    </section>
  </Collapsible>;
}
export default PivotSection;
