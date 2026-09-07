import Collapsible from '../../components/Collapsible';
import DataTimestamp from '../../components/ui/DataTimestamp';
import { BREAK, DIRECTION, TREND } from '../../content/momentum';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { breakPotential, momentumTarget, touchingLevel,
  type PanelLevel } from '../../domain/momentum/breakPotential';
import { money, pct2 } from '../../lib/format';
import type { Momentum } from '../../services/api/momentum';
import { useDashboard } from '../dashboard/DashboardContext';

const directionArrow = (direction: Momentum['direction']) =>
  direction === 'UP' ? '↑' : direction === 'DOWN' ? '↓' : '↔';

export function MomentumStrength({ momentum }: { momentum: Momentum }) {
  return <div className={`momentum-strength ${DIRECTION[momentum.direction].tone}`}>
    <div className="momentum-strength-heading"><span>Momentum gücü</span>
      <strong>{momentum.strength}<small> / 100</small></strong></div>
    <div className="momentum-strength-track" role="meter" aria-label="Momentum gücü"
      aria-valuemin={0} aria-valuemax={100} aria-valuenow={momentum.strength}
      aria-valuetext={`${momentum.strength} / 100; momentum ${TREND[momentum.trend]}`}>
      <i className="momentum-strength-fill" style={{ width: `${momentum.strength}%` }}/>
    </div>
    <div className="momentum-strength-scale" aria-hidden="true"><span>Zayıf</span><span>Güçlü</span></div>
  </div>;
}

/** Genel bakışta tek bir özet; ayrıntılı hesap ve seviye analizi teknik sekmede. */
export function MomentumSummary({ onOpen }: { onOpen?: () => void }) {
  const { momentum } = useDashboard();
  return <section className="momentum-summary" aria-label="Gün içi momentum özeti">
    <div className="momentum-summary-heading"><h2>Momentum</h2>
      {onOpen && <button type="button" onClick={onOpen}>Ayrıntılar <span aria-hidden="true">↗</span></button>}</div>
    {!momentum ? <p className="analysis-empty">Gün içi momentum verisi bekleniyor.</p> : <>
      <MomentumStrength momentum={momentum}/>
      <div className="momentum-summary-direction">
        <b className={DIRECTION[momentum.direction].tone}>{directionArrow(momentum.direction)} {DIRECTION[momentum.direction].label}</b>
        <span>{TREND[momentum.trend]}</span>
      </div>
      <p className="momentum-summary-note">5 dakikalık hareket · seans oynaklığına göre</p>
      <DataTimestamp time={momentum.asOf} staleAfterMs={15 * 60 * 1000}/>
    </>}
  </section>;
}

/**
 * Seviyeler **pivot kartıyla aynı kaynaktan** gelir; grafiğin altındaki özet
 * kartlarla birebir aynı sayılar. Momentum servisinin kendi merdiveni de var
 * ama iki liste farklı seviyeler içerince aynı ekranda iki farklı "ilk direnç"
 * görünüyordu.
 */
function LevelCard({ item, price, barSigmaPct, kind, hedef }: {
  item: PanelLevel | null; price: number; barSigmaPct: number;
  kind: 'sup' | 'res'; hedef: boolean;
}) {
  const title = kind === 'sup' ? 'En yakın destek' : 'En yakın direnç';
  if (!item) {
    return <article className={`momentum-level ${kind}`}>
      <span>{title}</span><strong>—</strong>
      <small>Fiyat merdivenin bu ucunun dışında</small>
    </article>;
  }
  const uzaklik = Math.abs(item.value / price - 1);
  const sigma = barSigmaPct > 0 ? uzaklik / (barSigmaPct / 100) : null;
  return (
    <article className={`momentum-level ${kind}${hedef ? ' target' : ''}`}>
      <span>{title}{hedef && <em> · yön referansı</em>}</span>
      <strong>{money(item.value)}</strong>
      {/* Uzaklık hem yüzde hem "kaç seans dalgalanması" olarak: ikincisi
          seansın kendi ölçeğinde ne kadar uzak olduğunu söyler. */}
      <small>{item.name} · {pct2(uzaklik)} uzakta
        {sigma !== null && <> · {sigma.toFixed(1)} seans dalgalanması</>}</small>
    </article>
  );
}

/**
 * Gün içi momentum ve kırılım gücü. Tüm eşikler o seansın oynaklığına göre
 * uyarlanır; hesap `market-service/momentum_service.py` içinde.
 */
function MomentumSection({ focus }: { focus?: string }) {
  const { momentum, pivotLadder, spot, harem } = useDashboard();
  const feature = featureBy('feature-momentum');
  if (!momentum) return <Collapsible id="momentum" anchor="feature-momentum"
    openByDefault={focus === feature.slug} title="Momentum ve seviye gücü" hint={feature.summary}>
    <section className="panel block terminal-momentum"><p className="analysis-empty">Gün içi momentum verisine şu anda ulaşılamıyor.</p></section>
  </Collapsible>;

  const yon = DIRECTION[momentum.direction];

  /* Seviye kaynağı panelin pivot merdiveni; fiyat da kartlarla aynı fiyat.
     Momentum yalnız **yönü, gücü ve seansın beklenen hareketini** sağlar. */
  const price = harem.satis || spot.price;
  const items = pivotLadder?.items ?? [];
  const resistance = items.filter(i => i.above).at(-1) ?? null;
  const support = items.find(i => !i.above) ?? null;
  const barSigmaPct = momentum.session.volatilityPct;

  const hedef = momentumTarget(momentum.direction, support, resistance);
  const guc = hedef
    ? breakPotential(hedef.level.value, price,
        momentum.session.expectedMove / momentum.price, momentum.strength)
    : null;
  const temas = touchingLevel(items, price, barSigmaPct);
  const hedefTaraf = hedef?.side;

  return (
    <Collapsible id="momentum" anchor="feature-momentum"
      openByDefault={focus === PANEL_FEATURES.find(f => f.anchor === 'feature-momentum')?.slug}
      title="Momentum ve seviye gücü" hint={feature.summary}
      summary={`${yon.label} · güç ${momentum.strength}`}>
      <section className="panel block terminal-momentum" aria-labelledby="pulse-title">
        <div className="analysis-heading"><div>
          <span className="analysis-kicker">Gün içi hareket</span>
          <h2 id="pulse-title">Momentum ve seviye gücü</h2>
        </div><span className="analysis-tag">5 dakikalık veri</span></div>
        <p className="analysis-intro">
          Aşağıdaki sayılar <b>son seansın</b> 5 dakikalık fiyat hareketinden gelir ve
          hepsi <b>bu seansın kendi dalgalanmasına</b> göre ölçeklenir. Sabit bir eşik
          yoktur: aynı 10 dolarlık hareket sakin bir günde güçlü, çalkantılı bir günde
          zayıf okunur.
        </p>
        <div className="momentum-source"><DataTimestamp time={momentum.asOf} staleAfterMs={15 * 60 * 1000}/></div>

        <div className="momentum-overview">
          <MomentumStrength momentum={momentum}/>
          <dl className="momentum-readings">
            <div><dt>Hareket yönü</dt><dd className={yon.tone}>{directionArrow(momentum.direction)} {yon.label}</dd><small>{yon.note}</small></div>
            <div><dt>Momentum eğilimi</dt><dd>{TREND[momentum.trend]}</dd><small>{momentum.session.bars} mum değerlendirildi</small></div>
          </dl>
        </div>

        {temas && (
          <p className="analysis-note">
            Fiyat şu an <b>{temas.name} · {money(temas.value)}</b> seviyesinin gürültü kadar
            yakınında — aradaki mesafe seansın kendi dalgalanmasından küçük, yani bu seviye
            <b> şu anda test ediliyor</b> ve kırılması olağan.
          </p>
        )}

        <div className="momentum-levels">
          <LevelCard item={support} price={price} barSigmaPct={barSigmaPct}
            kind="sup" hedef={hedefTaraf === 'support'}/>
          <LevelCard item={resistance} price={price} barSigmaPct={barSigmaPct}
            kind="res" hedef={hedefTaraf === 'resistance'}/>
        </div>

        {hedef && guc ? (
          <div className={`momentum-break ${BREAK[guc.strength].tone}`}>
            <div className="momentum-break-heading">
              <span>{hedef.side === 'support' ? 'İlk desteği' : 'İlk direnci'} kırma gücü</span>
              <b>{BREAK[guc.strength].label}</b>
            </div>
            <p>
              Hedef <b>{hedef.level.name} · {money(hedef.level.value)}</b>, yani{' '}
              <b>{money(Math.abs(hedef.level.value - price))}</b> uzakta. Seansın kalan{' '}
              {momentum.session.remainingBars} mumunda beklenen hareket{' '}
              <b>{pct2(momentum.session.expectedMove / momentum.price)}</b> —{' '}
              {BREAK[guc.strength].note}.
            </p>
            <small>Bu gösterge bir kırılım olasılığı yüzdesi değildir.</small>
          </div>
        ) : (
          <p className="analysis-empty">
            {momentum.direction === 'NEUTRAL'
              ? 'Hareket seansın kendi dalgalanmasından ayırt edilemiyor; yön belirginleşmediği için kırılım referansı seçilmedi.'
              : 'Fiyat merdivenin bu ucunun dışında; kırılacak bir sonraki seviye seçili pivot döneminde tanımlı değil.'}
          </p>
        )}

        <details className="analysis-method">
          <summary>Bu skor neyden oluşuyor?</summary>
          <ul>
            <li><b>Hız</b> — son bir saatteki birikmiş hareket, rastgele yürüyüşten
              beklenen dağılıma bölünür: {momentum.components.velocity?.toFixed(2) ?? '—'}</li>
            <li><b>Sürüklenme</b> — seans açılışından bu yana biriken hareket. Hız yalnız
              son bir saate bakar; gün boyu süren yavaş bir trendi bu satır yakalar:{' '}
              {momentum.components.drift?.toFixed(2) ?? '—'}</li>
            <li><b>İvme</b> — bu saatin hızı ile bir önceki saatinki arasındaki fark:{' '}
              {momentum.components.acceleration?.toFixed(2) ?? '—'}</li>
            <li><b>RSI</b> — gün içi momentum göstergesi, ortası sıfıra çekilmiş:{' '}
              {momentum.components.rsi?.toFixed(2) ?? '—'}</li>
            <li><b>MACD</b> — histogram, fiyat oynaklığına bölünmüş:{' '}
              {momentum.components.macd?.toFixed(2) ?? '—'}</li>
            <li><b>Hacim</b> — {momentum.session.hasVolume
              ? <>son bir saatin hacmi seans medyanına göre: {momentum.components.volume?.toFixed(2)}</>
              : <>bu seansta hacim verisi gelmiyor; hesap hacimsiz kuruldu</>}</li>
          </ul>
          <p className="momentum-meta">
            Seansın gün içi oynaklığı: mum başına {pct2(momentum.session.volatilityPct / 100)}.
            {' '}{momentum.session.bars} mum işlendi.
            Bu bölüm bir işlem tavsiyesi değildir; seviyelerin kırılması olağandır.
          </p>
        </details>
      </section>
    </Collapsible>
  );
}

export default MomentumSection;
