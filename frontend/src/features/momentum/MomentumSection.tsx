import Collapsible from '../../components/Collapsible';
import DataTimestamp from '../../components/ui/DataTimestamp';
import InfoTooltip from '../../components/ui/InfoTooltip';
import { BREAK, DIRECTION, MOMENTUM_DAILY, TREND, type DailyNote } from '../../content/momentum';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { BREAKOUT_SIDE, BREAKOUT_SIDE_TITLE, EXPECTED_MOVE_FRAME, FRAME, LEVEL_ROLE, MARKET_STATE, NOTE_TEXT,
  SERVICE_UNREACHABLE, SOURCE_TYPE, STATUS_TEXT, STRENGTH3, TEST_INTENSITY,
  sourceLabel, type BlockStatus, type SourceType, type TechnicalNote } from '../../content/technical';
import { money, money2, pct2, shortDate, signedPct2 } from '../../lib/format';
import type { Momentum } from '../../services/api/momentum';
import type { Breakout, BreakoutSide, BreakoutSideKey, Levels, MomentumDaily, Reference, SessionMeta, Zone }
  from '../../services/api/technical';
import { useDashboard } from '../dashboard/DashboardContext';
import { sessionStaleAfterMs } from '../dashboard/useTechnical';

/*
 * Bu dosyada finansal hesap yoktur. Uzaklık, yüzde, ATR/σ katı, hedef seçimi
 * ve kırılım gücü `GET /v1/market/xau/technical` yanıtından olduğu gibi
 * basılır; DTO'da olmayan sayı hesaplanmaz, yerine blok durumunun metni yazılır.
 */

const directionArrow = (direction: Momentum['direction']) =>
  direction === 'UP' ? '↑' : direction === 'DOWN' ? '↓' : '↔';

/** Blok/yan durumu → cümle. `OK` ama blok düşmüşse (şema reddi) ya da anahtar tanınmıyorsa genel yedek. */
const statusText = (status: string | null | undefined, fallback = 'Veri bekleniyor'): string =>
  (status && status in STATUS_TEXT ? STATUS_TEXT[status as BlockStatus] : null) ?? fallback;
const noteText = (note: string | null | undefined): string | null =>
  note && note in NOTE_TEXT ? NOTE_TEXT[note as TechnicalNote] : null;
const sourceTypeText = (type: string): string => type in SOURCE_TYPE ? SOURCE_TYPE[type as SourceType] : type;
const signed = (value: number, digits = 0) => `${value > 0 ? '+' : ''}${value.toFixed(digits)}`;
/** ATR/σ katları ve ağırlıklar Türkçe ondalıkla; `lib/format` yalnız para ve yüzde biçimler. */
const dec1 = (value: number) => new Intl.NumberFormat('tr-TR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(value);

/**
 * Servis hiç ulaşılamıyorsa "bekleniyor" demek yanıltır; blok durumu yoksa ve
 * teknik paket `fallback`'teyse ortak "ulaşılamadı" cümlesi yazılır.
 */
const emptyText = (status: string | null | undefined, unreachable: boolean): string =>
  statusText(status, unreachable ? SERVICE_UNREACHABLE : 'Veri bekleniyor');

/** Seans zaman damgası + piyasa durumu; eşik merdivenle ortak (`sessionStaleAfterMs`). */
function SessionStamp({ time, meta }: { time: string | null; meta: SessionMeta | null }) {
  const state = meta?.marketState ? MARKET_STATE[meta.marketState] : null;
  return <div className="momentum-source">
    <DataTimestamp time={time} staleAfterMs={sessionStaleAfterMs(meta)}/>
    {state && <span className={`momentum-market-state ${state.tone}`}> · {state.label}</span>}
  </div>;
}

/** Yatay 0–100 çubuğu; seans gücü, günlük skor ve iki kırılım yanı aynı bileşeni kullanır. */
function StrengthBar({ title, value, tone, valueText, scale = [STRENGTH3.WEAK.label, STRENGTH3.STRONG.label] }: {
  title: string; value: number; tone: string; valueText: string; scale?: [string, string];
}) {
  return <div className={`momentum-strength ${tone}`}>
    <div className="momentum-strength-heading"><span>{title}</span>
      <strong>{value}<small> / 100</small></strong></div>
    <div className="momentum-strength-track" role="meter" aria-label={title}
      aria-valuemin={0} aria-valuemax={100} aria-valuenow={value} aria-valuetext={valueText}>
      <i className="momentum-strength-fill" style={{ width: `${value}%` }}/>
    </div>
    <div className="momentum-strength-scale" aria-hidden="true"><span>{scale[0]}</span><span>{scale[1]}</span></div>
  </div>;
}

export function MomentumStrength({ momentum }: { momentum: Momentum }) {
  return <StrengthBar title="Momentum gücü" value={momentum.strength} tone={DIRECTION[momentum.direction].tone}
    valueText={`${momentum.strength} / 100; momentum ${TREND[momentum.trend]}`}/>;
}

/**
 * Günlük bileşik momentum bir **rejim** okumasıdır (son haftalar ne kadar tek
 * yönlü ve kararlı); "devam eder" demez. Skor 50 merkezli: 0 aşağı, 100 yukarı.
 */
function DailyMomentum({ daily, status, unreachable }: { daily: MomentumDaily | null; status: string | undefined; unreachable: boolean }) {
  if (!daily) return <div className="momentum-daily">
    <p className="momentum-summary-note"><b>Günlük momentum</b> · {emptyText(status, unreachable)}</p>
  </div>;
  const yon = MOMENTUM_DAILY.direction[daily.direction];
  const guc = MOMENTUM_DAILY.strength[daily.strength];
  const egilim = MOMENTUM_DAILY.trend[daily.trend];
  const not = daily.note && daily.note in MOMENTUM_DAILY.note ? MOMENTUM_DAILY.note[daily.note as DailyNote] : null;
  return <div className="momentum-daily">
    <StrengthBar title="Günlük momentum" value={daily.score} tone={yon.tone} scale={['Aşağı baskın', 'Yukarı baskın']}
      valueText={`${daily.score} / 100; ${yon.label}, ${guc.label}, ${egilim}`}/>
    <div className="momentum-summary-direction">
      <b className={yon.tone}>{yon.label}</b>
      <span>{guc.label} · {egilim} · Δ {signed(daily.delta)}</span>
    </div>
    <p className="momentum-summary-note">
      Günlük mumlardan rejim okuması{daily.date && <> · {shortDate(daily.date, true)}</>}
      {not && <> · <em>{not}</em></>}
    </p>
  </div>;
}

/** Genel bakışta tek bir özet; ayrıntılı hesap ve seviye analizi teknik sekmede. */
export function MomentumSummary({ onOpen }: { onOpen?: () => void }) {
  const { momentum, momentumDaily, technical, technicalStatus, sessionMeta } = useDashboard();
  const unreachable = technical === null && technicalStatus === 'fallback';
  return <section className="momentum-summary" aria-label="Momentum özeti">
    <div className="momentum-summary-heading"><h2>Momentum</h2>
      {onOpen && <button type="button" onClick={onOpen}>Ayrıntılar <span aria-hidden="true">↗</span></button>}</div>
    {!momentum ? <p className="analysis-empty">{emptyText(sessionMeta?.status ?? technical?.status.session, unreachable)}</p> : <>
      <MomentumStrength momentum={momentum}/>
      <div className="momentum-summary-direction">
        <b className={DIRECTION[momentum.direction].tone}>{directionArrow(momentum.direction)} {DIRECTION[momentum.direction].label}</b>
        <span>{TREND[momentum.trend]}</span>
      </div>
      <p className="momentum-summary-note">5 dakikalık hareket · seans oynaklığına göre</p>
      <SessionStamp time={momentum.asOf} meta={sessionMeta}/>
    </>}
    <DailyMomentum daily={momentumDaily} status={technical?.status.momentum_daily} unreachable={unreachable}/>
  </section>;
}

/** Bölge kartı: sayıların hepsi `levels.zones[]` alanı; güç iddia değil, temas tarihçesi. */
function ZoneCard({ zone, kind, status, hedef }: {
  zone: Zone | null; kind: 'sup' | 'res'; status: string; hedef: boolean;
}) {
  const role = kind === 'sup' ? LEVEL_ROLE.NEAREST_DOWN : LEVEL_ROLE.NEAREST_UP;
  if (!zone) {
    return <article className={`momentum-level ${kind}`}>
      <span>{role.label}</span><strong>—</strong>
      <small>{statusText(status)}</small>
    </article>;
  }
  const kaynaklar = zone.sources
    .map(s => `${sourceTypeText(s.sourceType)} · ${sourceLabel(s.label)} · ${money(s.price)}${s.date ? ` (${shortDate(s.date, true)})` : ''}`)
    .join(' — ');
  return (
    <article className={`momentum-level ${kind}${hedef ? ' target' : ''}`}>
      <span>{role.label}{hedef && <em> · kırılım hedefi</em>}</span>
      <strong>{money(zone.mid)}</strong>
      <small>{sourceLabel(zone.name)} · bölge {money(zone.low)}–{money(zone.high)}</small>
      {/* Uzaklık işaretli gelir: destek eksi, direnç artı. Katlar günlük ATR ve
          günlük σ; eski "seans dalgalanması" etiketi yanlış birimdi. */}
      <small>{signedPct2(zone.distancePct)} · {money(zone.distanceUsd)}
        {zone.distanceAtr !== null && <> · {dec1(zone.distanceAtr)} günlük ATR</>}
        {zone.distanceSigma !== null && <> · {dec1(zone.distanceSigma)} günlük σ</>}</small>
      <small>{zone.touches > 0 ? `${zone.touches} temas` : 'hiç test edilmedi'}
        {zone.lastTouch && <> · son test {shortDate(zone.lastTouch, true)}</>} · {TEST_INTENSITY[zone.label]}</small>
      {/* `<details>` akış içeriği; `<small>` içine konunca içerik modeli bozuluyordu. */}
      <div className="momentum-level-sources"><small>{zone.rejections} red · {zone.breaks} kırılım · {zone.sources.length} kaynak</small>
        <InfoTooltip label="Bölgenin kaynakları">{kaynaklar || 'Kaynak listesi gelmedi'}</InfoTooltip></div>
    </article>
  );
}

function LevelsBlock({ levels, breakout, reference, status, unreachable }: {
  levels: Levels | null; breakout: Breakout | null; reference: Reference | null; status: string | undefined; unreachable: boolean;
}) {
  if (!levels) return <p className="analysis-empty">{emptyText(status, unreachable)}</p>;
  const zoneOf = (id: string | null) => (id && levels.zones.find(z => z.id === id)) || null;
  const destek = zoneOf(levels.nearestSupport);
  const direnc = zoneOf(levels.nearestResistance);
  /* Başlık yanının hedefi hangi bölgeyse o kart işaretlenir; yön yoksa hiçbiri. */
  const hedefId = breakout?.headline ? breakout[breakout.headline].target?.zoneId ?? null : null;
  const testEdilen = levels.testing.map(id => { const z = zoneOf(id); return z ? `${sourceLabel(z.name)} · ${money(z.mid)}` : id; });
  return <>
    <p className="momentum-reference">
      Hesaplama referansı: {reference?.value != null
        ? <><b>{money2(reference.value)}</b> · {FRAME[reference.frame]}</>
        : statusText(reference?.status)}
      {levels.asOf && <> · bölgeler {shortDate(levels.asOf, true)}</>}
      {noteText(reference?.note) && <> · {noteText(reference?.note)}</>}
    </p>
    <div className="momentum-levels">
      <ZoneCard zone={destek} kind="sup" status={levels.sideStatus.support} hedef={!!destek && destek.id === hedefId}/>
      <ZoneCard zone={direnc} kind="res" status={levels.sideStatus.resistance} hedef={!!direnc && direnc.id === hedefId}/>
    </div>
    {testEdilen.length > 0 && (
      <p className="analysis-note">
        <b>{LEVEL_ROLE.TESTING.label}:</b> {testEdilen.join(', ')}. Fiyat bu bölgenin gürültü
        marjı içinde; test edilen bölge hedef alınmaz, kartlar bir sonraki bölgeyi gösterir.
      </p>
    )}
  </>;
}

/** Kırılım yanı; iki yan her zaman çizilir, yalnız `headline` olan vurgulanır. */
function BreakoutCard({ side, yan, headline }: { side: BreakoutSide; yan: BreakoutSideKey; headline: boolean }) {
  const title = BREAKOUT_SIDE_TITLE[yan];
  const etiket = side.label ? BREAK[side.label] : null;
  const not = noteText(side.note);
  const parca = (key: 'session' | 'daily') => key in side.components ? side.components[key].toFixed(2) : '—';
  /* `OK` yan hedef/güç/etiket taşır (ayrıştırıcı garantisi); diğer her durum yalnız metin. */
  const hedef = side.status === 'OK' ? side.target : null;
  const guc = side.strength;
  return (
    <article className={`momentum-break ${etiket?.tone ?? 'none'}${headline ? ' headline' : ''}`} aria-label={title}>
      <div className="momentum-break-heading">
        <span>{title}{headline && <em> · seans yönü</em>}</span>
        {etiket && <b>{etiket.label}</b>}
      </div>
      {!hedef || guc === null || !etiket ? <>
        <p>{statusText(side.status, 'Bu yan için güç ölçülemedi')}</p>
        {not && <small>{not}</small>}
      </> : <>
        <StrengthBar title={BREAKOUT_SIDE[yan]} value={guc} tone={etiket.tone} valueText={`${guc} / 100; ${etiket.label}`}/>
        <p>
          Hedef <b>{sourceLabel(hedef.name)} · {money(hedef.value)}</b>
          {side.distanceUsd !== null && <>, <b>{money(side.distanceUsd)}</b> uzakta</>}
          {side.distanceAtr !== null && <> ({dec1(side.distanceAtr)} günlük ATR)</>} — {etiket.note}.
        </p>
        <small>seans {parca('session')} · günlük {parca('daily')}</small>
        {not && <small className="momentum-break-note">{not}</small>}
      </>}
    </article>
  );
}

function BreakoutBlock({ breakout, momentum, status, unreachable }: {
  breakout: Breakout | null; momentum: Momentum | null; status: string | undefined; unreachable: boolean;
}) {
  if (!breakout) return <p className="analysis-empty">{emptyText(status, unreachable)}</p>;
  const cerceve = breakout.expectedMoveFrame ? EXPECTED_MOVE_FRAME[breakout.expectedMoveFrame] : null;
  return <>
    <p className="momentum-expected">
      Beklenen hareket: {breakout.expectedMove !== null
        ? <b>{money(breakout.expectedMove)}{breakout.expectedMovePct !== null && <> ({pct2(breakout.expectedMovePct)})</>}</b>
        : <b>—</b>}
      {cerceve && <> · {cerceve}</>}
      {momentum && breakout.expectedMoveFrame === 'session_remaining' && <> · kalan {momentum.session.remainingBars} mum</>}
      {' '}· ağırlık seans {dec1(breakout.weights.session)} / günlük {dec1(breakout.weights.daily)}
    </p>
    {!breakout.headline && (
      <p className="momentum-summary-note">Seans yönsüz olduğu için öne çıkarılan bir yan yok; iki yan da ölçüldü.</p>
    )}
    <div className="momentum-breaks">
      <BreakoutCard side={breakout.up} yan="up" headline={breakout.headline === 'up'}/>
      <BreakoutCard side={breakout.down} yan="down" headline={breakout.headline === 'down'}/>
    </div>
    {/* Her zaman görünür: skor bir olasılık değil, ulaşma × itme × sönüm ölçüsü. */}
    <p className="analysis-note">{NOTE_TEXT.NOT_A_PROBABILITY}.{noteText(breakout.note) && breakout.note !== 'NOT_A_PROBABILITY' && <> {noteText(breakout.note)}.</>}</p>
  </>;
}

/**
 * Gün içi momentum, test edilmiş bölgeler ve iki yanlı kırılım gücü. Hesabın
 * tamamı `market-service/technical/` içinde; burada yalnız DTO gösterilir.
 */
function MomentumSection({ focus }: { focus?: string }) {
  const { momentum, levels, breakout, reference, technical, technicalStatus, sessionMeta } = useDashboard();
  const feature = featureBy('feature-momentum');
  const yon = momentum ? DIRECTION[momentum.direction] : null;
  const unreachable = technical === null && technicalStatus === 'fallback';

  return (
    <Collapsible id="momentum" anchor="feature-momentum"
      openByDefault={focus === PANEL_FEATURES.find(f => f.anchor === 'feature-momentum')?.slug}
      title="Momentum ve seviye gücü" hint={feature.summary}
      summary={momentum && yon ? `${yon.label} · güç ${momentum.strength}` : undefined}>
      <section className="panel block terminal-momentum" aria-labelledby="pulse-title">
        <div className="analysis-heading"><div>
          <span className="analysis-kicker">Gün içi hareket</span>
          <h2 id="pulse-title">Momentum ve seviye gücü</h2>
        </div><span className="analysis-tag">5 dakikalık veri</span></div>
        <p className="analysis-intro">
          Momentum <b>son seansın</b> 5 dakikalık fiyat hareketinden gelir ve <b>bu seansın
          kendi dalgalanmasına</b> göre ölçeklenir. Sabit bir eşik yoktur: aynı 10 dolarlık
          hareket sakin bir günde güçlü, çalkantılı bir günde zayıf okunur. Seviyeler ve
          kırılım gücü ise günlük mumlardan, aynı vadeli fiyat çerçevesinde hesaplanır.
        </p>
        {momentum && <SessionStamp time={momentum.asOf} meta={sessionMeta}/>}

        {momentum && yon ? (
          <div className="momentum-overview">
            <MomentumStrength momentum={momentum}/>
            <dl className="momentum-readings">
              <div><dt>Hareket yönü</dt><dd className={yon.tone}>{directionArrow(momentum.direction)} {yon.label}</dd><small>{yon.note}</small></div>
              <div><dt>Momentum eğilimi</dt><dd>{TREND[momentum.trend]}</dd><small>{momentum.session.bars} mum değerlendirildi</small></div>
            </dl>
          </div>
        ) : (
          <p className="analysis-empty">{emptyText(sessionMeta?.status ?? technical?.status.session, unreachable)}</p>
        )}

        <h3 className="momentum-subhead">Seviyeler</h3>
        <LevelsBlock levels={levels} breakout={breakout} reference={reference} status={technical?.status.levels} unreachable={unreachable}/>

        <h3 className="momentum-subhead">Kırılım gücü</h3>
        <BreakoutBlock breakout={breakout} momentum={momentum} status={technical?.status.breakout} unreachable={unreachable}/>

        {momentum && (
          <details className="analysis-method">
            <summary>Seans skoru neyden oluşuyor?</summary>
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
        )}
      </section>
    </Collapsible>
  );
}

export default MomentumSection;
