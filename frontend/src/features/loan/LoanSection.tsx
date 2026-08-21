import Collapsible from '../../components/Collapsible';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { pct, tryAmount, tryMoney, tryRate } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

function LoanSection({ focus }: { focus?: string }) {
  const { loanTerm, setLoanTerm, loanAmount, setLoanAmount, loanRate, setLoanRate, futureUsdTry, setFutureUsdTry, loan, costs } = useDashboard();
  const loanCosts = costs;
  return (
    <Collapsible id="loan" anchor="feature-tl" openByDefault={focus===PANEL_FEATURES.find(f=>f.anchor==="feature-tl")?.slug} title={featureBy("feature-tl").title} hint={featureBy("feature-tl").summary} summary={`${loanTerm} ay`}>
    <section className="panel block loan-break-even" aria-labelledby="finance-comparison-title">
    <div className="loan-head">
    <div><span className="eyebrow">Varsayımsal karşılaştırma</span>
    <h2 id="finance-comparison-title">Altının TL getirisi ve finansman maliyeti</h2><p>Ons senaryosu, canlı USD/TL kuru ve vade sonu kur varsayımıyla TL getirisine çevrilir.</p></div>
    <div className="segmented">{[3,6,9].map(n=><button key={n} className={loanTerm===n?'active':''} onClick={()=>setLoanTerm(n)}>{n} Ay</button>)}</div></div>
    <div className="loan-inputs">
    <label>Karşılaştırma tutarı (TL)<input type="text" inputMode="numeric" autoComplete="off" value={tryAmount(loanAmount)} onChange={e=>setLoanAmount(Number(e.target.value.replace(/\D/g,""))||0)}/></label>
    <label>Aylık finansman maliyeti (%)<input type="number" min="0" step="0.01" value={loanRate} onChange={e=>setLoanRate(+e.target.value)}/></label>
    <div><span>Canlı USD/TL</span><b>{loanCosts.currentFx?`₺${tryRate(loanCosts.currentFx)}`:'Bekleniyor'}</b></div>
    <label>Vade sonu USD/TL varsayımı<input type="number" min="0" step="0.01" placeholder={loanCosts.currentFx?String(loanCosts.currentFx):''} value={futureUsdTry||''} onChange={e=>setFutureUsdTry(+e.target.value)}/></label>
    <div><span>Toplam finansman maliyeti</span><b>{tryMoney(loanCosts.total)}</b></div></div>
    <div className="loan-results">{loanCosts.results.map(s=>
    <article className={`loan-result ${s.tone}`} key={s.label}><span>{s.label} · Ons {pct(s.onsReturn)} · TL {pct(s.tlReturn)}</span><strong className={s.net>=0?'positive':'negative'}>{s.net>=0?'+':''}{tryMoney(s.net)}</strong>
    <small>{loanTerm} ay sonunda TL getirisi–maliyet farkı</small></article>)}</div><details className="break-even-details"><summary>Teorik başa baş oranlarını göster</summary>
    <div className="loan-scenarios">{loanCosts.results.map(s=>
    <article className={`loan-scenario ${s.tone}`} key={s.label}><span>{s.label}</span><strong>{s.monthly==null?'%0,00':`%${(s.monthly*100).toFixed(2).replace('.',',')}`}</strong>
    <small>TL getirisine göre aylık teorik başa baş maliyeti</small></article>)}</div></details>
    <div className="loan-note">Başlangıçta canlı USD/TL satış kuru kullanılır. Vade sonu kur alanı boşsa kurun değişmediği varsayılır; makas, vergi, sigorta ve diğer masraflar dahil değildir.{loan.derived&&<em> 9 aylık sonuç, modelin 6 aylık eğiliminden türetilmiştir.</em>}</div></section>
    </Collapsible>
  );
}

export default LoanSection;
