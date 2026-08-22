import { useState } from 'react';
import Collapsible from '../../components/Collapsible';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import type { Impact } from '../../domain/model/impacts';
import { money, pct } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

const TOP = 5;

const UNUSUAL_TEXT = {
  normal: 'her zamanki seviyesinde',
  high: 'normalden uzakta',
  extreme: 'olağandışı bir seviyede',
} as const;

const usd = (value: number) => `${value >= 0 ? '+' : '−'}${money(Math.abs(value))}`;

function Row({ item }: { item: Impact }) {
  return (
    <li className={`push ${item.value >= 0 ? 'up' : 'down'}`}>
      <div className="push-head">
        <span className="push-name">{item.label}</span>
        <b className="push-usd">{usd(item.usd)}</b>
      </div>
      <div className="push-bar"><i style={{ width: `${Math.max(4, item.share * 100)}%` }}/></div>
      <p className="push-why">{item.hint}{' '}
        <span className={`push-level ${item.unusualness}`}>Şu an {UNUSUAL_TEXT[item.unusualness]}.</span></p>
    </li>
  );
}

function ImpactSection({ focus }: { focus?: string }) {
  const { impacts, confident, forecast, horizonDays } = useDashboard();
  const [all, setAll] = useState(false);
  const feature = featureBy('feature-katki');

  const index = Math.max(0, forecast.horizons.indexOf(impacts.horizon));
  const hasView = confident[index] !== false;
  const up = all ? impacts.up : impacts.up.slice(0, TOP);
  const down = all ? impacts.down : impacts.down.slice(0, TOP);
  const hidden = impacts.up.length + impacts.down.length - up.length - down.length;
  const target = impacts.price * (1 + impacts.here);

  return (
    <Collapsible id="impact" anchor="feature-katki"
      openByDefault={focus === PANEL_FEATURES.find(f => f.anchor === 'feature-katki')?.slug}
      title={feature.title} hint={feature.summary}
      summary={impacts.live && hasView ? impacts.up[0]?.label ?? null : null}>
      <section className="panel block impact-block" aria-labelledby="impact-title">
        <h2 id="impact-title">Model bu tahmini neden verdi?</h2>

        {!impacts.live
          ? <p className="impact-empty">Model servisine ulaşılamıyor; hangi göstergenin
              tahmini nasıl etkilediği gösterilemiyor.</p>
          : !hasView
            ? <p className="impact-empty">Model {horizonDays} günlük vadede yön bildirmiyor,
                bu yüzden ayrıştıracak bir tahmin de yok. Yön bildirdiği bir vadeyi seçin.</p>
            : <>
              <p className="impact-lede">
                Bugün ons altın <b>{money(impacts.price)}</b>. Model {impacts.horizon} gün sonrası
                için <b>{money(target)}</b> bekliyor — yani <b>{usd(impacts.hereUsd)}</b>.
                Bu beklentiyi oluşturan göstergeler aşağıda: bazıları fiyatı yukarı itiyor,
                bazıları aşağı çekiyor. Yanlarındaki tutar, <b>o gösterge tek başına</b> beklentiyi
                kaç dolar oynattığını söyler.
              </p>

              <div className="push-columns">
                <div className="push-group up">
                  <h3>Yukarı itenler <b>{usd(impacts.upUsd)}</b></h3>
                  <ul>{up.map(item => <Row key={item.key} item={item}/>)}</ul>
                </div>
                <div className="push-group down">
                  <h3>Aşağı çekenler <b>{usd(impacts.downUsd)}</b></h3>
                  <ul>{down.map(item => <Row key={item.key} item={item}/>)}</ul>
                </div>
              </div>

              {hidden > 0 && <button type="button" className="push-more" onClick={() => setAll(true)}>
                Etkisi daha küçük {hidden} göstergeyi de göster</button>}
              {all && <button type="button" className="push-more" onClick={() => setAll(false)}>
                Yalnız en güçlüleri göster</button>}

              <p className="impact-net">
                Yukarı itenler <b className="positive">{usd(impacts.upUsd)}</b>, aşağı çekenler{' '}
                <b className="negative">{usd(impacts.downUsd)}</b> — ikisi birbirini büyük ölçüde
                götürüyor ve geriye <b>{usd(impacts.netUsd)}</b> kalıyor. Modelin
                {' '}{impacts.horizon} günlük beklentisi bu: <b>{pct(impacts.here)}</b>.
              </p>

              <details className="impact-how">
                <summary>Bu sayılar nasıl bulunuyor?</summary>
                <p>Her gösterge için şu soru sorulur: “Bu gösterge bugünkü değerinde değil de
                  kendi uzun dönem ortalamasında olsaydı, model kaç dolar farklı bir sayı
                  söylerdi?” Aradaki fark o göstergenin etkisi olarak yazılır.</p>
                <p>Bu bir <b>duyarlılık</b> ölçüsüdür, sebep-sonuç değil. “Enflasyon yükseldiği
                  için altın çıkacak” demez; “model, enflasyon bu seviyede olduğu için daha
                  yüksek bir sayı söylüyor” der. Model doğrusal olmadığından tek tek etkiler
                  tam olarak toplanmak zorunda da değildir.</p>
              </details>
            </>}
      </section>
    </Collapsible>
  );
}

export default ImpactSection;
