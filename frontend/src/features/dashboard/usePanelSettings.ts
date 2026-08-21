import { useState } from 'react';

/** Yalnızca görünümü etkileyen tercihler; hiçbiri hesaba girmez.
 *  Ekran genişliği burada tutulmuyor: grafik kendi kutusunu ResizeObserver ile
 *  ölçüyor, böylece JS eşiği ile CSS kırılma noktası ayrışamıyor. */
export const usePanelSettings = () => {
  const [wideChart, setWideChart] = useState(true);
  const [rangeDays, setRangeDays] = useState(90);
  const [horizonDays, setHorizonDays] = useState(90);
  const [showBand, setShowBand] = useState(true);
  const [showLevels, setShowLevels] = useState(false);
  const [showOrigin, setShowOrigin] = useState(true);
  const [showSR, setShowSR] = useState(true);
  const [pivotPeriod, setPivotPeriod] = useState<'weekly' | 'monthly'>('weekly');
  const [pivotMethod, setPivotMethod] = useState<'classic' | 'fib'>('classic');
  const [capital, setCapital] = useState(10000);
  const [riskPct, setRiskPct] = useState(1);
  const [loanTerm, setLoanTerm] = useState(6);
  const [loanAmount, setLoanAmount] = useState(100000);
  const [loanRate, setLoanRate] = useState(4.25);
  const [futureUsdTry, setFutureUsdTry] = useState(0);

  return {
    wideChart, setWideChart,
    rangeDays, setRangeDays, horizonDays, setHorizonDays,
    showBand, setShowBand, showLevels, setShowLevels, showOrigin, setShowOrigin, showSR, setShowSR,
    pivotPeriod, setPivotPeriod, pivotMethod, setPivotMethod,
    capital, setCapital, riskPct, setRiskPct,
    loanTerm, setLoanTerm, loanAmount, setLoanAmount, loanRate, setLoanRate, futureUsdTry, setFutureUsdTry,
  };
};

export type PanelSettings = ReturnType<typeof usePanelSettings>;
