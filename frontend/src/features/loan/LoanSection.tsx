import { useMinVisible } from '../../app/useMinVisible';
import Spinner from '../../components/Spinner';
import Collapsible from '../../components/Collapsible';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { HORIZON_LABELS } from '../../content/site';
import { pct, tryAmount, tryMoney, tryRate } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

function LoanSection({ focus }: { focus?: string }) {
  const {
    horizonDays, setHorizonDays, loanAmount, setLoanAmount, loanRate, setLoanRate,
    futureUsdTry, setFutureUsdTry, loan, costs, forecast, confident, modelStatus,
  } = useDashboard();

  const index = Math.max(0, forecast.horizons.indexOf(loan.days));
  const hasView = confident[index] !== false;
  const busy = useMinVisible(modelStatus === 'loading');
  const ready = modelStatus === 'live' && hasView && !busy;

  return (
    <Collapsible id="loan" anchor="feature-tl"
      openByDefault={focus === PANEL_FEATURES.find(f => f.anchor === 'feature-tl')?.slug}
      title={featureBy('feature-tl').title} hint={featureBy('feature-tl').summary}
      summary={`${loan.days} gün`}>
      <section className="panel block loan-break-even" aria-labelledby="finance-comparison-title">
        <div className="loan-head">
          <div>
            <span className="eyebrow">Varsayımsal karşılaştırma</span>
            <h2 id="finance-comparison-title">Altının TL getirisi ve finansman maliyeti</h2>
            <p>Modelin <b>{loan.days} günlük</b> ons senaryosu, canlı USD/TL kuru ve vade sonu kur
              varsayımıyla TL getirisine çevrilir; aynı sürenin finansman maliyetiyle karşılaştırılır.</p>
          </div>
          {/* Vade modelin ufkuyla aynı: 3/6/9 ay sunuluyordu ve 30 günlük tahmin
              9 katına kadar üstel olarak uzatılıyordu. */}
          <div className="segmented">{forecast.horizons.map(n =>
            <button type="button" key={n} className={horizonDays === n ? 'active' : ''}
              aria-pressed={horizonDays === n} onClick={() => setHorizonDays(n)}>
              {HORIZON_LABELS[n] ?? `${n} Gün`}</button>)}</div>
        </div>

        <div className="loan-inputs">
          <label>Karşılaştırma tutarı (TL)
            <input type="text" inputMode="numeric" autoComplete="off" value={tryAmount(loanAmount)}
              onChange={e => setLoanAmount(Number(e.target.value.replace(/\D/g, '')) || 0)}/></label>
          <label>Aylık finansman maliyeti (%)
            <input type="number" min="0" step="0.01" value={loanRate}
              onChange={e => setLoanRate(+e.target.value)}/></label>
          <div><span>Canlı USD/TL</span>
            <b>{costs.currentFx ? `₺${tryRate(costs.currentFx)}` : 'Bekleniyor'}</b></div>
          <label>Vade sonu USD/TL varsayımı
            <input type="number" min="0" step="0.01" placeholder={costs.currentFx ? String(costs.currentFx) : ''}
              value={futureUsdTry || ''} onChange={e => setFutureUsdTry(+e.target.value)}/></label>
          <div><span>{loan.days} günlük finansman maliyeti</span>
            <b>{tryMoney(costs.total)}<em> · {pct(costs.costRate)}</em></b></div>
        </div>

        {!ready && busy
          ? <div className="loading-row"><Spinner size="md" label="Model sonucu bekleniyor…"/></div>
          : !ready
          ? <p className="loan-note">{modelStatus !== 'live'
              ? 'Aktif model sonucu gelmeden altın getirisi ve finansman karşılaştırması gösterilmez.'
              : `Model ${loan.days} günlük vadede yön bildirmiyor; bu vade için karşılaştırma üretilmez.`}</p>
          : <>
            <div className="loan-results">{costs.results.map(s =>
              <article className={`loan-result ${s.tone}`} key={s.label}>
                <span>{s.label} · Ons {pct(s.onsReturn)} · TL {pct(s.tlReturn)}</span>
                <strong className={s.net >= 0 ? 'positive' : 'negative'}>
                  {s.net >= 0 ? '+' : ''}{tryMoney(s.net)}</strong>
                <small>{loan.days} gün sonunda TL kazancı eksi finansman maliyeti</small>
              </article>)}
            </div>

            <details className="break-even-details">
              <summary>Teorik başa baş oranlarını göster</summary>
              <div className="loan-scenarios">{costs.results.map(s =>
                <article className={`loan-scenario ${s.tone} ${s.monthly == null ? 'none' : ''}`} key={s.label}>
                  <span>{s.label}</span>
                  <strong>{s.monthly == null ? 'Başa baş yok'
                    : `%${(s.monthly * 100).toFixed(2).replace('.', ',')}`}</strong>
                  <small>{s.monthly == null
                    ? 'Bu senaryoda altın TL bazında kazandırmıyor; hiçbir finansman maliyeti karşılanmaz.'
                    : 'Bu senaryoyu karşılayan azami aylık maliyet'}</small>
                </article>)}
              </div>
            </details>

            <div className="loan-note">Başlangıçta canlı USD/TL satış kuru kullanılır. Vade sonu kur alanı
              boşsa kurun değişmediği varsayılır; bu durumda TL getirisi ons getirisine eşit çıkar.
              Makas, vergi, sigorta ve diğer masraflar dahil değildir. Senaryolar modelin
              {' '}{loan.days} günlük ufkundan gelir; daha uzun vadeye uzatılmaz.</div>
          </>}
      </section>
    </Collapsible>
  );
}

export default LoanSection;
