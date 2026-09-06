import { useMemo, useState } from 'react';
import type { PivotMethod, PivotPeriod } from '../../services/api/technical';

/** Yalnızca görünümü etkileyen tercihler; hiçbiri hesaba girmez.
 *  Ekran genişliği burada tutulmuyor: grafik kendi kutusunu ResizeObserver ile
 *  ölçüyor, böylece JS eşiği ile CSS kırılma noktası ayrışamıyor. */
export const usePanelSettings = () => {
  const [rangeDays, setRangeDays] = useState(90);
  /* Varsayılan 14 idi; modelin ağırlığı orada 0,13, yani fiilen "görüş yok".
     30 gün hem en yüksek beceriye (%26) hem anlamlı ağırlığa sahip. */
  const [horizonDays, setHorizonDays] = useState(30);
  const [showBand, setShowBand] = useState(true);
  const [showLevels, setShowLevels] = useState(false);
  const [showSR, setShowSR] = useState(true);
  /* Pivot dönemi ve yöntemi sunucunun sözlüğüyle aynı adları taşır
     (`/v1/market/xau/technical?pivot_method=&pivot_period=`); merdiven orada
     kurulur. Varsayılan haftalık + klasik: teknik paketin varsayılanıyla aynı,
     böylece ilk yanıt ek istek gerektirmez. Eski 'fib'/'classic'/'weekly'/
     'monthly' değerleri hiçbir yerde saklanmıyordu, taşınacak kayıt yok. */
  const [pivotPeriod, setPivotPeriod] = useState<PivotPeriod>('WEEKLY');
  const [pivotMethod, setPivotMethod] = useState<PivotMethod>('CLASSIC');
  const [capital, setCapital] = useState(10000);
  const [riskPct, setRiskPct] = useState(1);
  const [loanAmount, setLoanAmount] = useState(100000);
  const [loanRate, setLoanRate] = useState(4.25);
  const [futureUsdTry, setFutureUsdTry] = useState(0);

  /* Kimliği sabit tutulur: aksi hâlde her canlı tick'te tüm panel yeniden çizilir. */
  return useMemo(() => ({
    rangeDays, setRangeDays, horizonDays, setHorizonDays,
    showBand, setShowBand, showLevels, setShowLevels, showSR, setShowSR,
    pivotPeriod, setPivotPeriod, pivotMethod, setPivotMethod,
    capital, setCapital, riskPct, setRiskPct,
    loanAmount, setLoanAmount, loanRate, setLoanRate, futureUsdTry, setFutureUsdTry,
  }), [rangeDays, horizonDays, showBand, showLevels, showSR,
       pivotPeriod, pivotMethod, capital, riskPct, loanAmount, loanRate, futureUsdTry]);
};

export type PanelSettings = ReturnType<typeof usePanelSettings>;
