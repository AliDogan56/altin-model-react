import { Fragment, useState } from 'react';
import Collapsible from '../../components/Collapsible';
import { INDICATOR_NAME, INDICATOR_STATE, WARMING_UP, indicatorExtraText, maPosition, type IndicatorKey } from '../../content/indicators';
import { MOMENTUM_DAILY } from '../../content/momentum';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { FRAME, STATUS_TEXT } from '../../content/technical';
import { longDate, money, money2 } from '../../lib/format';
import type { IndicatorRow, Indicators, MomentumDaily } from '../../services/api/technical';
import { useDashboard } from '../dashboard/DashboardContext';

/*
 * Teknik göstergeler: sunucunun `indicators` bloğunun **görüntüsü**. Hesap,
 * eşik ve durum sunucuda (`technical/indicators.py`); burada yalnız biçim ve
 * sözlük var. Bir sayı DTO'da yoksa hesaplanmaz, ilgili durum metni yazılır.
 */

/** Açıklamalar `IndicatorKey` ile anahtarlı; periyotlar sunucu varsayılanları (`IndicatorParams`). */
const EXPLANATION: Record<IndicatorKey, string> = {
  rsi: 'Son 14 günlük fiyat hareketlerinin göreli gücünü gösterir (Wilder). Aşırı alım ve aşırı satım bölgeleri, tek başına fiyatın döneceği anlamına gelmez.',
  stochastic: 'Kapanışın son 14 günün en yüksek ve en düşük fiyatına göre konumunu gösterir. %D, kısa dönemli yumuşatılmış karşılaştırma çizgisidir.',
  williams: 'Kapanışın son 14 günlük fiyat aralığındaki konumunu −100 ile 0 arasında gösterir. Uç bölgeler trend boyunca korunabilir.',
  cci: 'Fiyatın 20 günlük ortalamasından sapmasını ölçer. Yüksek mutlak değerler ortalamadan daha belirgin bir uzaklığa işaret eder.',
  macd: '12 ve 26 dönemlik üstel ortalamaların farkıdır. Durum, MACD değerinin 9 dönemlik sinyal çizgisine göre konumunu gösterir.',
  adx: 'Trendin yönünden bağımsız olarak gücünü ölçer (Wilder). +DI ve −DI değerleri yükseliş ve düşüş hareketlerini karşılaştırmaya yardımcı olur.',
  atr: 'Son 14 günlük gerçek fiyat aralığının Wilder ortalaması, dolar cinsinden. Oynaklık durumu, son 100 günün medyanıyla karşılaştırılarak belirlenir.',
  roc: 'Son kapanışın 12 gün önceki kapanışa göre yüzdesel değişimidir. Pozitif ve negatif değerler değişimin yönünü gösterir.',
};
const EXPLANATION_FALLBACK = 'Bu gösterge günlük XAU/USD kapanışlarından sunucuda hesaplanır.';

/** Yön oku yalnız işaretli göstergelerde anlamlı; RSI'nin "üstünde" oku olmaz. */
const DIRECTIONAL: ReadonlySet<string> = new Set(['macd', 'roc']);

const fixed = (digits: number) => new Intl.NumberFormat('tr-TR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
/** tr-TR biçim, tipografik eksi; sözlükteki ikinci satırla aynı görünüm. */
const dec = (value: number, digits = 1) => fixed(digits).format(value).replace(/^-/, '−');

/** Değer biçimi göstergeye göre: ATR dolar, ROC yüzde, kalanı bir ondalık. Biçimdir, hesap değil. */
const valueText = (row: IndicatorRow): string => {
  if (row.value === null) return '—';
  if (row.key === 'atr') return money2(row.value);
  if (row.key === 'roc') return `%${dec(row.value, 2)}`;
  return dec(row.value);
};

const nameOf = (key: string): string => (INDICATOR_NAME as Record<string, string | undefined>)[key] ?? key.toUpperCase();
const explanationOf = (key: string): string => (EXPLANATION as Record<string, string | undefined>)[key] ?? EXPLANATION_FALLBACK;

/**
 * Blok durum cümlesi. `status` DTO'da düz `string`; sözlükte olmayan bir durum
 * (sunucu yeni değer ekledi) boş kart yerine genel bir cümleyle karşılanır.
 */
const statusText = (status: string): string =>
  (STATUS_TEXT as Record<string, string | null | undefined>)[status] ?? 'Gösterge bloğu bu yanıtta yok';

/**
 * Günlük momentum tek satır: skor bir **rejim betimlemesi** (son haftaların
 * yönü ve kararlılığı), getiri beklentisi değil — doğrulama raporu düşük
 * skorun bu seride "dip yakını" çıktığını ölçtü, "devam eder" dili yasak.
 */
function MomentumTile({ momentum }: { momentum: MomentumDaily }) {
  const direction = MOMENTUM_DAILY.direction[momentum.direction];
  const strength = MOMENTUM_DAILY.strength[momentum.strength];
  const note = momentum.note === 'CONFLICTING' ? MOMENTUM_DAILY.note.CONFLICTING : null;
  return (
    <div className="tech-row indicator-momentum">
      <span>
        Günlük momentum
        <em>{momentum.date ? `${longDate(momentum.date)} · ` : ''}rejim betimlemesi, yön beklentisi değil{note ? ` · ${note}` : ''}</em>
      </span>
      <b>{momentum.score}/100</b>
      <em className={`tech-state ${direction.tone}`}>{direction.label} · {strength.label} · {MOMENTUM_DAILY.trend[momentum.trend]}</em>
    </div>
  );
}

function IndicatorTables({ block }: { block: Indicators }) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const toggle = (key: string) => setExpanded(previous => {
    const next = new Set(previous);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  });

  return (
    <>
      <table className="indicator-table">
        <caption className="market-table-sr-only">Günlük XAU/USD teknik gösterge değerleri ve durumları</caption>
        <thead><tr><th scope="col">Gösterge</th><th scope="col">Değer</th><th scope="col">Durum</th></tr></thead>
        <tbody>{block.rows.map(row => {
          const isExpanded = expanded.has(row.key);
          const detailId = `indicator-explanation-${row.key}`;
          /* Değer ya da durum yoksa gösterge ısınıyor: pencere kadar mum gelmemiş. */
          const state = row.value === null || row.state === null ? WARMING_UP : INDICATOR_STATE[row.state];
          const extra = indicatorExtraText(row.key, row.extra);
          const arrow = DIRECTIONAL.has(row.key) && row.state !== null && (state.tone === 'up' ? '↑' : state.tone === 'down' ? '↓' : null);
          return <Fragment key={row.key}>
            <tr className={isExpanded ? 'is-expanded' : undefined}>
              <th scope="row"><button type="button" className="indicator-name" aria-expanded={isExpanded} aria-controls={detailId} onClick={() => toggle(row.key)}>
                <span className="indicator-toggle" aria-hidden="true">{isExpanded ? '−' : '+'}</span>
                <span>{nameOf(row.key)}{extra && <small>{extra}</small>}</span>
              </button></th>
              <td className="indicator-value">{valueText(row)}</td>
              <td><span className={`indicator-state ${state.tone}`}>
                {arrow && <span aria-hidden="true">{arrow} </span>}
                {state.label}
              </span></td>
            </tr>
            <tr className="indicator-explanation" id={detailId} hidden={!isExpanded}>
              <td colSpan={3}><p>{explanationOf(row.key)}</p></td>
            </tr>
          </Fragment>;
        })}</tbody>
      </table>
      <div className="indicator-subhead"><h3>Hareketli ortalamalar</h3><span>USD / ons · {FRAME.daily_close}</span></div>
      {block.movingAverages.length ? (
        <table className="indicator-table indicator-table--averages">
          <caption className="market-table-sr-only">Basit ve üstel hareketli ortalamalar; son günlük kapanışın basit ortalamaya göre konumu</caption>
          <thead><tr><th scope="col">Dönem</th><th scope="col"><abbr title="Basit hareketli ortalama">SMA</abbr></th><th scope="col"><abbr title="Üstel hareketli ortalama">EMA</abbr></th><th scope="col">Fiyatın konumu</th></tr></thead>
          <tbody>{block.movingAverages.map(row => {
            const position = maPosition(row.priceAboveSma);
            return <tr key={row.period}>
              <th scope="row">MA{row.period}</th>
              <td className="indicator-value">{row.sma === null ? '—' : money(row.sma)}</td>
              <td className="indicator-value">{row.ema === null ? '—' : money(row.ema)}</td>
              <td><span className={`indicator-state ${position.tone}`}>
                {position.tone === 'up' && <span aria-hidden="true">↑ </span>}
                {position.tone === 'down' && <span aria-hidden="true">↓ </span>}
                {position.label}
              </span></td>
            </tr>;
          })}</tbody>
        </table>
      ) : <p className="market-table-empty">{statusText('INSUFFICIENT_DATA')}</p>}
    </>
  );
}

function IndicatorsSection({ focus }: { focus?: string }) {
  const { technical, technicalStatus, indicators: block, momentumDaily } = useDashboard();
  const feature = featureBy('feature-teknik');
  const rsi = block?.rows.find(row => row.key === 'rsi');
  const summary = rsi && rsi.value !== null ? `RSI ${dec(rsi.value)}` : 'RSI —';

  /* Boş durum aynı kabuğun içinde: kart kaybolmaz, neden boş olduğu yazılır. */
  const empty = !technical
    ? (technicalStatus === 'loading' ? 'Teknik analiz yükleniyor…' : statusText('NO_DATA'))
    : block ? null : statusText(technical.status.indicators);
  const headerLine = block
    ? `Günlük XAU/USD${block.date ? ` · ${longDate(block.date)} kapanışı` : ''} · ${block.bars} mum`
    : 'Günlük XAU/USD · Gösterge durumları';

  return (
    <Collapsible id="tech" anchor="feature-teknik" openByDefault={focus === PANEL_FEATURES.find(f => f.anchor === 'feature-teknik')?.slug} title={feature.title} hint={feature.summary} summary={summary}>
      <section className="panel block tech-block indicator-panel" aria-labelledby="tech-title">
        <div className="market-table-head">
          <div><h2 id="tech-title">Teknik göstergeler</h2><p>{headerLine}</p></div>
          {block && <span className="market-table-help">Açıklama için göstergeyi açın</span>}
        </div>
        {momentumDaily && <MomentumTile momentum={momentumDaily}/>}
        {empty
          ? <p className="market-table-empty" role="status">{empty}</p>
          : block && <IndicatorTables block={block}/>}
        <p className="market-table-note">Fiyatın konumu, son günlük kapanışın SMA değerine göre durumudur; ATR ve 100 günlük medyanı dolar cinsinden, sunucunun verdiği gibi yazılır. Göstergeler alım-satım kararı üretmez; aşırı alım bölgesi yükselişin biteceği anlamına gelmez ve güçlü trendlerde gösterge uzun süre aynı bölgede kalabilir.</p>
      </section>
    </Collapsible>
  );
}

export default IndicatorsSection;
