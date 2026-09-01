import Collapsible from '../../components/Collapsible';
import { BREAK, DIRECTION, TREND } from '../../content/momentum';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { breakPotential, momentumTarget, touchingLevel,
  type PanelLevel } from '../../domain/momentum/breakPotential';
import { money, pct2 } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

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
  const title = kind === 'sup' ? 'Aşağıda ilk destek' : 'Yukarıda ilk direnç';
  if (!item) {
    return <article className={`pulse-level ${kind}`}>
      <span>{title}</span><strong>—</strong>
      <small>Fiyat merdivenin bu ucunun dışında</small>
    </article>;
  }
  const uzaklik = Math.abs(item.value / price - 1);
  const sigma = barSigmaPct > 0 ? uzaklik / (barSigmaPct / 100) : null;
  return (
    <article className={`pulse-level ${kind}${hedef ? ' target' : ''}`}>
      <span>{title}{hedef && <em> · hedef</em>}</span>
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
  if (!momentum) return null;

  const feature = featureBy('feature-momentum');
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
      title={feature.title} hint={feature.summary}
      summary={`${yon.label} · güç ${momentum.strength}`}>
      <section className="panel block pulse-block" aria-labelledby="pulse-title">
        <h2 id="pulse-title">Şu anki hareket bir seviyeyi kırabilir mi?</h2>
        <p className="pulse-lede">
          Aşağıdaki sayılar <b>bugünün</b> 5 dakikalık fiyat hareketinden gelir ve
          hepsi <b>bu seansın kendi dalgalanmasına</b> göre ölçeklenir. Sabit bir eşik
          yoktur: aynı 10 dolarlık hareket sakin bir günde güçlü, çalkantılı bir günde
          zayıf okunur.
        </p>

        <div className="pulse-head">
          <article className={`pulse-dial ${yon.tone}`}>
            <span>Yön</span>
            <strong>{yon.label}</strong>
            <small>{yon.note}</small>
          </article>

          <article className="pulse-score">
            <span>Momentum gücü</span>
            <strong>{momentum.strength}<em>/100</em></strong>
            <div className="pulse-bar" role="img"
              aria-label={`Momentum gücü 100 üzerinden ${momentum.strength}`}>
              <i className={yon.tone} style={{ width: `${momentum.strength}%` }}/>
            </div>
            <small>Momentum <b>{TREND[momentum.trend]}</b></small>
          </article>
        </div>

        {temas && (
          <p className="pulse-touching">
            Fiyat şu an <b>{temas.name} · {money(temas.value)}</b> seviyesinin gürültü kadar
            yakınında — aradaki mesafe seansın kendi dalgalanmasından küçük, yani bu seviye
            <b> şu anda test ediliyor</b> ve kırılması olağan.
          </p>
        )}

        <div className="pulse-levels">
          <LevelCard item={support} price={price} barSigmaPct={barSigmaPct}
            kind="sup" hedef={hedefTaraf === 'support'}/>
          <LevelCard item={resistance} price={price} barSigmaPct={barSigmaPct}
            kind="res" hedef={hedefTaraf === 'resistance'}/>
        </div>

        {hedef && guc ? (
          <div className={`pulse-break ${BREAK[guc.strength].tone}`}>
            <div className="pulse-break-head">
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
          </div>
        ) : (
          <p className="pulse-empty">
            {momentum.direction === 'NEUTRAL'
              ? 'Hareket seansın kendi dalgalanmasından ayırt edilemiyor; yön belirginleşmeden bir seviyenin kırılacağını söylemek uydurma olur.'
              : 'Fiyat merdivenin bu ucunun dışında; kırılacak bir sonraki seviye seçili pivot döneminde tanımlı değil.'}
          </p>
        )}

        <details className="pulse-detail">
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
          <p className="pulse-meta">
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
