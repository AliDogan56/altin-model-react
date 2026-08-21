import { featureBy } from '../../content/panel';
import { model } from '../../data/artifact';
import { BAND_COVERAGE } from '../../domain/model/predict';
import { money, pct2, signedPct2 } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';

function ScorecardSection() {
  const { scorecard } = useDashboard();
  return (
    <section id="feature-karne" className="panel block score-block" aria-labelledby="score-title">
              <div className="score-head">
                <div><span className="eyebrow">Modelin kendi karnesi</span>
                  <h2 id="score-title">{featureBy("feature-karne").title}</h2>
                  <p>{model.latestDate} tarihinde ilan edilen tahmin, o günden bu yana gerçekleşen kapanışlarla karşılaştırılıyor. Her yeni günle bir ölçüm daha ekleniyor.</p></div>
                <div className="score-days"><b>{scorecard.days}</b><span>gün<br/>gerçekleşti</span></div>
              </div>
              <div className="score-grid">
                <div><span>Ortalama mutlak hata</span><b>{pct2(scorecard.mae)}</b>
                  <small>Tahmin ile gerçekleşen arasındaki ortalama sapma</small></div>
                <div><span>Naif kural ("fiyat değişmez")</span><b>{pct2(scorecard.naiveMae)}</b>
                  <small>Hiçbir bilgi kullanmayan referans</small></div>
                <div className={scorecard.skill>0?'good':'bad'}>
                  <span>Modelin katkısı</span>
                  <b>{scorecard.skill>=0?'+':''}{new Intl.NumberFormat('tr-TR',{maximumFractionDigits:0}).format(scorecard.skill*100)}%</b>
                  <small>{scorecard.skill>0?'naif kuraldan bu kadar daha isabetli':'naif kural bu kadar daha isabetli — model henüz değer katmıyor'}</small></div>
                <div><span>Bant isabeti</span><b>{scorecard.inBand}/{scorecard.days}</b>
                  <small>İlan edilen %{BAND_COVERAGE} bandın içinde kalan gün sayısı</small></div>
                <div><span>Yön isabeti</span><b>{scorecard.rightWay}/{scorecard.days}</b>
                  <small>Yükselir/düşer yönünü doğru bilen gün sayısı</small></div>
                <div><span>En büyük sapma</span><b>{signedPct2(scorecard.worst.errorPct)}</b>
                  <small>{new Date(`${scorecard.worst.date}T00:00:00`).toLocaleDateString('tr-TR')} · tahmin {money(scorecard.worst.v)} · gerçek {money(scorecard.worst.real)}</small></div>
              </div>
              <p className="score-note">{scorecard.days<20
                ? `Uyarı: ${scorecard.days} günlük ölçüm istatistiksel bir sonuç için çok azdır; bu rakamlar şimdilik yalnız şeffaflık amacıyla gösterilir. Anlamlı bir yargı için en az birkaç ay gerekir.`
                : 'Ölçüm penceresi genişledikçe bu rakamlar daha güvenilir hâle gelir.'}</p>
            </section>
  );
}

export default ScorecardSection;
