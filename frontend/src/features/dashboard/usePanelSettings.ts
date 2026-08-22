import { useMemo, useState } from 'react';

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
  const [showOrigin, setShowOrigin] = useState(false);
  const [showSR, setShowSR] = useState(true);
  const [pivotPeriod, setPivotPeriod] = useState<'weekly' | 'monthly'>('weekly');
  /* Varsayılan Fibonacci: seviyeler aralığın 0,382 / 0,618 / 1,0 katlarına oturduğu
     için klasik formüle göre fiyata daha yakın ve daha dengeli dağılır. */
  const [pivotMethod, setPivotMethod] = useState<'classic' | 'fib'>('fib');
  const [capital, setCapital] = useState(10000);
  const [riskPct, setRiskPct] = useState(1);
  const [loanAmount, setLoanAmount] = useState(100000);
  const [loanRate, setLoanRate] = useState(4.25);
  const [futureUsdTry, setFutureUsdTry] = useState(0);

  /* Kimliği sabit tutulur: aksi hâlde her canlı tick'te tüm panel yeniden çizilir. */
  return useMemo(() => ({
    rangeDays, setRangeDays, horizonDays, setHorizonDays,
    showBand, setShowBand, showLevels, setShowLevels, showOrigin, setShowOrigin, showSR, setShowSR,
    pivotPeriod, setPivotPeriod, pivotMethod, setPivotMethod,
    capital, setCapital, riskPct, setRiskPct,
    loanAmount, setLoanAmount, loanRate, setLoanRate, futureUsdTry, setFutureUsdTry,
  }), [rangeDays, horizonDays, showBand, showLevels, showOrigin, showSR,
       pivotPeriod, pivotMethod, capital, riskPct, loanAmount, loanRate, futureUsdTry]);
};

export type PanelSettings = ReturnType<typeof usePanelSettings>;
