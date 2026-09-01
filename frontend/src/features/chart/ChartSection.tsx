import { useMinVisible } from '../../app/useMinVisible';
import Spinner from '../../components/Spinner';
import { BREAK_SHORT, DIRECTION } from '../../content/momentum';
import { breakPotential, momentumTarget } from '../../domain/momentum/breakPotential';
import { featureBy } from '../../content/panel';
import { money, pct } from '../../lib/format';
import { useState } from 'react';
import { useDashboard } from '../dashboard/DashboardContext';
import ForecastChart from './ForecastChart';

const RANGES: [number, string][] = [[30, '1 Ay'], [90, '3 Ay'], [180, '6 Ay'], [260, '1 Yıl']];

function ChartSection() {
  const {
    history, candles, spot, harem, rangeDays, setRangeDays, horizonDays, setHorizonDays,
    showOrigin, setShowOrigin, forecast, originForecast, modelStatus, confident,
    pivotLadder, pivotPeriod, momentum,
  } = useDashboard();

  const price = harem.satis || spot.price;
  const index = Math.max(0, forecast.horizons.indexOf(horizonDays));
  const busy = useMinVisible(modelStatus === 'loading');
  /* Varsayılan çizgi: acemi okuyucu için en sade görünüm. Mum, gün içi
     dalgalanmayı görmek isteyen için bir adım ötesi. */
  const [candleMode, setCandleMode] = useState(false);
  const hasCandles = candles.length > 0;
  const showingCandles = candleMode && hasCandles;
  const available = modelStatus === 'live' && confident[index] !== false && !busy;
  const target = price * (1 + forecast.mean[index]);
  const low = price * (1 + forecast.mean[index] - forecast.err[index]);
  const high = price * (1 + forecast.mean[index] + forecast.err[index]);

  /* Seviyeler pivot kartıyla **aynı kaynaktan** gelir; iki bölüm farklı sayı
     gösterdiğinde hangisinin doğru olduğu anlaşılmıyordu. */
  const items = pivotLadder?.items ?? [];
  const resistance = items.filter(i => i.above).at(-1);   // fiyatın hemen üstü
  const support = items.find(i => !i.above);              // fiyatın hemen altı
  const periodLabel = pivotPeriod === 'monthly' ? 'Aylık' : 'Haftalık';
  const away = (level: number) => level / price - 1;

  /* Momentumun hedefi komşu kartın seviyesidir: yukarı yönlüyse ilk direnç,
     aşağı yönlüyse ilk destek. Aynı seçim Ayrıntılar'daki momentum bölümünde de
     kullanılır — seçim `domain/momentum` içinde, iki yerde ayrı yazılmaz.
     Hesap oransal: momentum gün içi vadeliden, kartlar spottan besleniyor ve
     aradaki ~%1 seviye farkı ancak oranda sadeleşir. */
  const pulseHedef = momentum ? momentumTarget(momentum.direction, support, resistance) : null;
  const pulseGuc = momentum && pulseHedef
    ? breakPotential(pulseHedef.level.value, price,
        momentum.session.expectedMove / momentum.price, momentum.strength)
    : null;
  const pulse = pulseHedef && pulseGuc
    ? { baslik: pulseHedef.side === 'resistance' ? 'İlk direnci' : 'İlk desteği', guc: pulseGuc }
    : null;

  return (
    <section id="feature-grafik" className="panel block chart-block">
      <div className="chart-head">
        <div>
          <h2>{featureBy('feature-grafik').title}</h2>
          <p>Sol taraf gerçekleşen fiyat, sağ taraf modelin beklentisi. Yatay çizgiler
            <b> destek (S1–S3)</b> ve <b>direnç (R1–R3)</b> seviyeleri — Ayrıntılar'daki
            Pivot kartıyla birebir aynı sayılar.</p>
        </div>
        <div className="chart-tools">
          <div className="tool-group"><span>Ne kadar geçmiş</span>
            <div className="segmented">{RANGES.map(([n, label]) =>
              <button type="button" key={n} className={rangeDays === n ? 'active' : ''}
                aria-pressed={rangeDays === n} onClick={() => setRangeDays(n)}>{label}</button>)}</div>
          </div>
          <div className="tool-group"><span>Görünüm</span>
            <div className="segmented">
              <button type="button" className={candleMode ? '' : 'active'} aria-pressed={!candleMode}
                onClick={() => setCandleMode(false)}>Çizgi</button>
              <button type="button" className={candleMode ? 'active' : ''} aria-pressed={candleMode}
                disabled={!hasCandles} title={hasCandles ? undefined : 'Günlük yüksek/düşük verisi bekleniyor'}
                onClick={() => setCandleMode(true)}>Mum</button>
            </div>
          </div>
          <div className="tool-group"><span>Kaç gün sonrası</span>
            <div className="segmented">{forecast.horizons.map(n =>
              <button type="button" key={n} className={horizonDays === n ? 'active' : ''}
                aria-pressed={horizonDays === n} onClick={() => setHorizonDays(n)}>{n} gün</button>)}</div>
          </div>
        </div>
      </div>

      <ForecastChart
        forecast={forecast} originForecast={originForecast} available={available}
        history={history} candles={candles} candleMode={candleMode}
        rangeDays={rangeDays} horizonDays={horizonDays}
        showOrigin={showOrigin} onToggleOrigin={() => setShowOrigin(v => !v)}
        levels={items} levelPeriod={periodLabel}
        spot={{ ...spot, price }} describedById="destek-direnc-aciklama"/>

      <div className="market-snapshot">
        <article className="snapshot-card now">
          <span>Şu anki fiyat</span>
          <strong>{money(price)}</strong>
          <small>ons altın · canlı</small>
        </article>
        <article className="snapshot-card support">
          <span>Aşağıda ilk destek</span>
          <strong>{support ? money(support.value) : '—'}</strong>
          <small>{support
            ? `${support.name} · ${pct(away(support.value))} uzakta`
            : 'Fiyat tüm seviyelerin altında'}</small>
        </article>
        <article className="snapshot-card resistance-card">
          <span>Yukarıda ilk direnç</span>
          <strong>{resistance ? money(resistance.value) : '—'}</strong>
          <small>{resistance
            ? `${resistance.name} · +${pct(away(resistance.value))} uzakta`
            : 'Fiyat tüm seviyelerin üzerinde'}</small>
        </article>
        {/* Gün içi momentum, **komşu kartların** seviyesinden bahseder: yukarı
            yönlüyse üstteki direnci, aşağı yönlüyse alttaki desteği kırma gücü.
            Momentum servisinin kendi merdiveni daha geniş (günlük + haftalık +
            salınım) ve başka bir seviye seçebiliyor; kartın komşusundan farklı
            bir sayı söylemesi kafa karıştırıyordu. */}
        {momentum && (
          <article className={`snapshot-card momentum-card ${DIRECTION[momentum.direction].tone}`}>
            <span>Gün içi momentum</span>
            <strong>{DIRECTION[momentum.direction].label} · {momentum.strength}</strong>
            <small>{pulse
              ? `${pulse.baslik} kırma gücü: ${BREAK_SHORT[pulse.guc.strength].toUpperCase()}`
              : momentum.direction === 'NEUTRAL'
                ? 'Yön belirginleşmeden seviye hedefi verilmiyor'
                : 'Bu yönde gösterilen seviye yok'}</small>
          </article>
        )}
        <article className="snapshot-card target">
          <span>{horizonDays} gün sonrası</span>
          <strong>{available ? money(target) : '—'}</strong>
          <small>{available
            ? `${pct(target / price - 1)} · ${money(low)}–${money(high)} arası`
            : modelStatus === 'live' ? 'Model bu vadede yön bildirmiyor'
            : busy ? <Spinner size="sm" label="Model bekleniyor" inline/>
            : 'Model servisi çevrimdışı'}</small>
        </article>
      </div>

      <div className="level-explainer" id="destek-direnc-aciklama">
        <h3>Bu çizgiler ne anlatıyor?</h3>
        <p className="level-source">Seviyeler <b>{periodLabel.toLowerCase()} pivot</b> yöntemiyle
          bulunur: önceki tam {pivotPeriod === 'monthly' ? 'ayın' : 'haftanın'} en yüksek, en düşük
          ve kapanış fiyatına standart bir formül uygulanır. Ayrıntılar bölümündeki
          <b> Pivot seviyeleri</b> kartında aynı sayılar merdiven düzeninde durur; dönem ve
          yöntemi oradan değiştirebilirsiniz.</p>
        <div className="level-cards">
          <div className="level-card sup">
            <b>Destek · S1 · S2 · S3</b>
            <p>{support
              ? <>Fiyatın hemen altındaki ilk zemin <b>{support.name}</b>, yani <b>{money(support.value)}</b>.
                  Fiyat düşerse ilk burada tepki beklenir; kırılırsa sıradaki destek devreye girer.</>
              : <>Fiyat şu an bu dönemin tüm seviyelerinin altında; aşağıda hesaplanmış bir destek kalmadı.</>}</p>
          </div>
          <div className="level-card res">
            <b>Direnç · R1 · R2 · R3</b>
            <p>{resistance
              ? <>Fiyatın hemen üstündeki ilk engel <b>{resistance.name}</b>, yani <b>{money(resistance.value)}</b>.
                  Yukarı hareket ilk burada zorlanır; aşılırsa sıradaki direnç hedef olur.</>
              : <>Fiyat şu an bu dönemin tüm seviyelerinin üzerinde; yukarıda hesaplanmış bir direnç kalmadı.</>}</p>
          </div>
        </div>
        {showingCandles && <p className="level-caveat candle-note">
          <b>Mumlar nasıl okunur?</b> İnce dikey çizgi (fitil) o günün <b>en yüksek ve
          en düşük</b> fiyatını, kalın gövde ise günün <b>net hareketini</b> gösterir:
          yeşil gövde önceki güne göre yükseliş, kırmızı düşüş. Fiyat kaynağı gün
          açılışını vermediği için gövdenin alt ucu <b>önceki günün kapanışıdır</b>;
          klasik mumdaki açılış yerine bu kullanılır. Fitildeki her sayı ölçülmüş veridir.</p>}
        <p className="level-caveat"><b>P</b> orta çizgidir (pivot noktası): fiyatın üstünde kalması
          olumlu, altına inmesi olumsuz okunur. Bu seviyeler geçmiş fiyattan formülle çıkarılır;
          garanti değildir, kırılmaları olağandır.</p>
      </div>
    </section>
  );
}

export default ChartSection;
