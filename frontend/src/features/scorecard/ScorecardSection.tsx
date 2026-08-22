import Collapsible from '../../components/Collapsible';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { pct, pct2 } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

/**
 * Modelin karnesi. Değerler servisin purge'lü walk-forward ölçümlerinden gelir:
 * her ufuk, eğitimde hiç görmediği 500'den fazla günde değerlendirilmiştir.
 */
function ScorecardSection({ focus }: { focus?: string }) {
  const { scorecard } = useDashboard();
  if (!scorecard) return null;

  const best = scorecard.rows.reduce((a, b) => (b.skill > a.skill ? b : a));

  return (
    <Collapsible id="score" anchor="feature-karne"
      openByDefault={focus === PANEL_FEATURES.find(f => f.anchor === 'feature-karne')?.slug}
      title={featureBy('feature-karne').title} hint={featureBy('feature-karne').summary}
      summary={`${best.horizon} günde ${pct(best.direction)} isabet`}>
      <section className="panel block score-block" aria-labelledby="score-title">
        <h2 id="score-title">Model ne kadar tutturuyor?</h2>
        <p className="score-lede">
          Her vade, modelin eğitimde <b>hiç görmediği</b> günlerde sınandı. Aşağıdaki üç sayı
          o sınavın sonucu: ne kadar yanılıyor, yönü ne sıklıkla doğru biliyor ve
          “fiyat olduğu yerde kalır” demekten daha iyi mi.
        </p>

        <div className="score-table" role="table" aria-label="Vade başına isabet ölçümleri">
          <div className="score-row head" role="row">
            <span role="columnheader">Vade</span>
            <span role="columnheader">Ortalama yanılma</span>
            <span role="columnheader">Yönü bilme</span>
            <span role="columnheader">Basit kurala üstünlük</span>
          </div>
          {scorecard.rows.map(row => (
            <div className={`score-row ${row.confident ? '' : 'muted'}`} role="row" key={row.horizon}>
              <span role="cell"><b>{row.horizon} gün</b><small>{row.oofRows} günde sınandı</small></span>
              <span role="cell" data-label="Ortalama yanılma: ">{pct2(row.mae)}</span>
              <span role="cell" data-label="Yönü bilme: "
                className={row.direction >= 0.6 ? 'positive' : undefined}>{pct(row.direction)}</span>
              <span role="cell" data-label="Basit kurala üstünlük: "
                className={row.skill > 0.05 ? 'positive' : row.skill <= 0 ? 'negative' : undefined}>
                {row.skill >= 0 ? '+' : ''}{pct(row.skill)}</span>
            </div>
          ))}
        </div>

        <p className="score-note">
          Soluk satırlar, modelin kendi ağırlığını kıstığı vadelerdir: orada panel fiyat
          tahmini yerine <b>“görüş yok”</b> gösterir.{' '}
          <span className="score-version">Aktif model: <code>{scorecard.version || 'bilinmiyor'}</code></span>
        </p>
      </section>
    </Collapsible>
  );
}

export default ScorecardSection;
