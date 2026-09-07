import { useState } from 'react';
import Collapsible from '../../components/Collapsible';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { IMPACT_LABELS } from '../../content/parameters';
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
    <li className={`contribution-row ${item.value >= 0 ? 'up' : 'down'}`}>
      <div className="contribution-label">
        <span>{item.label}</span>
        <b>{usd(item.usd)}</b>
      </div>
      <div className="contribution-track" aria-hidden="true">
        <span className="contribution-half negative">{item.value < 0 &&
          <i style={{ width: `${item.share * 100}%` }}/>}</span>
        <span className="contribution-half positive">{item.value >= 0 &&
          <i style={{ width: `${item.share * 100}%` }}/>}</span>
      </div>
      <details className="contribution-description">
        <summary>Göstergeyi yorumla</summary>
        <p>{item.hint}{' '}
          <span className={item.unusualness}>Şu an {UNUSUAL_TEXT[item.unusualness]}.</span></p>
      </details>
    </li>
  );
}

function ImpactSection({ focus }: { focus?: string }) {
  const { impacts, confident, forecast, horizonDays, neutralized, modelStatus } = useDashboard();
  const [all, setAll] = useState(false);
  const feature = featureBy('feature-katki');

  const index = Math.max(0, forecast.horizons.indexOf(impacts.horizon));
  const hasView = confident[index] !== false;
  const up = all ? impacts.up : impacts.up.slice(0, TOP);
  const down = all ? impacts.down : impacts.down.slice(0, TOP);
  const hidden = impacts.up.length + impacts.down.length - up.length - down.length;
  const target = impacts.price * (1 + impacts.here);
  const rows = [...up, ...down].sort((a, b) => Math.abs(b.usd) - Math.abs(a.usd));

  return (
    <Collapsible id="impact" anchor="feature-katki"
      openByDefault={focus === PANEL_FEATURES.find(f => f.anchor === 'feature-katki')?.slug}
      title="Modeli ne etkiliyor?" hint={feature.summary}
      summary={impacts.live && hasView ? impacts.up[0]?.label ?? null : null}>
      <section className="panel block terminal-impact" aria-labelledby="impact-title">
        <div className="analysis-heading"><div>
          <span className="analysis-kicker">Model açıklanabilirliği</span>
          <h2 id="impact-title">Modeli ne etkiliyor?</h2>
        </div><span className="analysis-tag">{impacts.horizon} günlük görünüm</span></div>
        {modelStatus === 'loading' && impacts.live && <p className="model-update" role="status">Önceki model sonucu ve girdileri gösteriliyor · güncelleniyor…</p>}

        {!impacts.live
          ? <p className="analysis-empty">Model servisine ulaşılamıyor; hangi göstergenin
              tahmini nasıl etkilediği gösterilemiyor.</p>
          : !hasView
            ? <p className="analysis-empty">Model {horizonDays} günlük vadede yön bildirmiyor,
                bu yüzden ayrıştıracak bir tahmin de yok. Yön bildirdiği bir vadeyi seçin.</p>
            : <>
              <p className="analysis-intro">
                Her çubuk, bir girdinin bugünkü değerinin model çıktısındaki dolar etkisini gösterir.
                Bu, modelin girdiye duyarlılığıdır; piyasa için bir sebep-sonuç ilişkisi değildir.
              </p>
              <dl className="contribution-context">
                <div><dt>Referans fiyat</dt><dd>{money(impacts.price)}</dd></div>
                <div><dt>Model beklentisi</dt><dd>{money(target)}</dd></div>
                <div><dt>Beklenen değişim</dt><dd>{usd(impacts.hereUsd)} <small>{pct(impacts.here)}</small></dd></div>
              </dl>

              {/* Donmuş girdi tahmine katılmadı; bunu saklamak, kartta neden
                  görünmediğini açıklamamak olurdu. */}
              {neutralized.length > 0 && <p className="analysis-note">
                <b>Hesaba katılmayan gösterge:</b>{' '}
                {neutralized.map(name => IMPACT_LABELS[name]?.label ?? name).join(', ')}.
                Uzun süredir hiç değişmediği için tahmin edilen dönem hakkında güncel bilgi
                taşımıyor; model bu göstergeye dayanmadan hesaplıyor.
              </p>}

              <div className="contribution-axis" aria-hidden="true">
                <span>← Negatif etki</span><span>Pozitif etki →</span>
              </div>
              <ul className="contribution-list" aria-label="Model girdilerinin tahmine etkisi">
                {rows.map(item => <Row key={item.key} item={item}/>)}
              </ul>
              {!rows.length && <p className="analysis-empty">Görünür eşik olan 1 doların üzerinde bir girdi etkisi bulunmuyor.</p>}

              {hidden > 0 && <button type="button" className="analysis-more" onClick={() => setAll(true)}>
                Etkisi daha küçük {hidden} göstergeyi de göster</button>}
              {all && <button type="button" className="analysis-more" onClick={() => setAll(false)}>
                Yalnız en güçlüleri göster</button>}

              <p className="analysis-note">
                Pozitif katkılar <b className="positive">{usd(impacts.upUsd)}</b>, negatif katkılar{' '}
                <b className="negative">{usd(impacts.downUsd)}</b>. Katkıların toplamı <b>{usd(impacts.netUsd)}</b>.
                Model doğrusal olmadığından bu toplam, modelin <b>{usd(impacts.hereUsd)}</b> beklentisiyle birebir eşleşmeyebilir.
              </p>

              <details className="analysis-method">
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
