import Collapsible from '../../components/Collapsible';
import InfoTooltip from '../../components/ui/InfoTooltip';
import { PANEL_FEATURES, featureBy } from '../../content/panel';
import { pct, pct2 } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

function MetricHeader({ label, explanation }: { label: string; explanation: string }) {
  return <span className="evaluation-column-label">{label}
    <InfoTooltip label={label}>{explanation}</InfoTooltip>
  </span>;
}

/**
 * Modelin karnesi. Değerler servisin purge'lü walk-forward ölçümlerinden gelir:
 * her ufuk, eğitimde hiç görmediği 500'den fazla günde değerlendirilmiştir.
 */
function ScorecardSection({ focus }: { focus?: string }) {
  const { scorecard } = useDashboard();
  return (
    <Collapsible id="score" anchor="feature-karne"
      openByDefault={focus === PANEL_FEATURES.find(f => f.anchor === 'feature-karne')?.slug}
      title="Tahmin performansı" hint={featureBy('feature-karne').summary}
      summary={scorecard ? `${scorecard.measuredDays} katman dışı gözlem` : 'Ölçümler bekleniyor'}>
      <section className="panel block terminal-evaluation" aria-labelledby="score-title">
        <div className="analysis-heading"><div>
          <span className="analysis-kicker">Model değerlendirmesi</span>
          <h2 id="score-title">Tahmin performansı</h2>
        </div><span className="analysis-tag">Walk-forward test</span></div>
        {!scorecard ? <p className="analysis-empty">Aktif modelin değerlendirme verilerine şu anda ulaşılamıyor.</p> : <>
          <p className="analysis-intro">
            Her vade, ilgili eğitim katında görülmeyen tarihlerde ölçüldü.
            Metrikler geçmiş test sonuçlarıdır; güncel tahminin doğruluk olasılığı değildir.
          </p>
          <table className="evaluation-table">
            <caption className="evaluation-caption">Vade başına katman dışı model ölçümleri. MAE getiri yüzdesi cinsindendir.</caption>
            <thead><tr>
              <th scope="col">Vade</th>
              <th scope="col"><MetricHeader label="MAE" explanation="Ortalama mutlak getiri hatası. Düşük değer daha az hata demektir. Servis bu metriği dolar değil, getiri oranı olarak sağlar."/></th>
              <th scope="col"><MetricHeader label="Yön isabeti" explanation="Tahmin edilen yönün gerçekleşen getiri yönüyle eşleştiği test gözlemlerinin oranı."/></th>
              <th scope="col"><MetricHeader label="Baseline'a göre" explanation="Fiyat değişmez (sıfır getiri) referansına göre beceri. Pozitif değer referanstan iyi, negatif değer daha zayıf sonucu belirtir."/></th>
              <th scope="col"><MetricHeader label="Test örneği" explanation="Modelin ilgili eğitim katında görmediği ve test edilen gözlem sayısı (n)."/></th>
            </tr></thead>
            <tbody>{scorecard.rows.map(row => (
              <tr key={row.horizon}>
                <th scope="row"><b>{row.horizon} gün</b><span className={`evaluation-status ${row.confident ? 'active' : ''}`}>{row.confident ? 'Görüş üretiyor' : 'Görüş yok'}</span></th>
                <td><span className="evaluation-mobile-label">MAE</span><b>{pct2(row.mae)}</b></td>
                <td><span className="evaluation-mobile-label">Yön isabeti</span><b>{pct(row.direction)}</b></td>
                <td><span className="evaluation-mobile-label">Baseline'a göre</span><b className={row.skill > 0 ? 'positive' : row.skill < 0 ? 'negative' : undefined}>{row.skill >= 0 ? '+' : '−'}{pct(Math.abs(row.skill))}</b></td>
                <td><span className="evaluation-mobile-label">Test örneği</span><b>{row.oofRows.toLocaleString('tr-TR')} <small>gözlem</small></b></td>
              </tr>
            ))}</tbody>
          </table>
          <details className="analysis-method evaluation-mobile-method">
            <summary>Metrikler nasıl okunur?</summary>
            <p><b>MAE:</b> ortalama mutlak getiri hatasıdır; düşük olması daha iyidir. Dolar cinsinden değildir.</p>
            <p><b>Yön isabeti:</b> yükseliş veya düşüş yönünün doğru tahmin edildiği test gözlemlerinin oranıdır.</p>
            <p><b>Baseline'a göre:</b> fiyatın değişmediğini varsayan referansa kıyasla beceridir. Pozitif değer referanstan daha iyi sonuçtur.</p>
            <p><b>Test örneği:</b> ilgili eğitim katında görülmeden değerlendirilen gözlem sayısıdır.</p>
          </details>
          <p className="analysis-note">“Görüş yok”, ilgili vadede model ağırlığının tahmin yayımlamak için yeterli olmadığı anlamına gelir. Bu ağırlık bir güven yüzdesi değildir.</p>
          <p className="evaluation-version">Aktif model <code>{scorecard.version || 'bilinmiyor'}</code></p>
        </>}
      </section>
    </Collapsible>
  );
}

export default ScorecardSection;
