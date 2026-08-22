import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { model } from '../../data/artifact';
import { IMPACT_LABELS } from '../../content/parameters';
import { indicators } from '../../domain/indicators';
import { computeImpacts } from '../../domain/model/impacts';
import { buildDailyPath, predict } from '../../domain/model/predict';
import { buildLadder, computePivots } from '../../domain/pivots';
import { loanCosts, loanProjection } from '../../domain/loan';
import { tradeZones } from '../../domain/tradeZones';
import { useForecastModel } from './useForecastModel';
import { useMarketData } from './useMarketData';
import { usePanelSettings } from './usePanelSettings';

const useDashboardState = () => {
  const market = useMarketData();
  const settings = usePanelSettings();
  const forecastModel = useForecastModel(market.live, market.lastClose, market.harem.satis ?? market.lastClose ?? market.spot.price);
  const { features, forecast, values } = forecastModel;

  const impacts = useMemo(
    () => computeImpacts(model, features, values.price, IMPACT_LABELS, forecast, settings.horizonDays),
    [features, values.price, forecast, settings.horizonDays]);

  const zones = useMemo(
    () => tradeZones(forecast, values.price, features.gold_atr14_pct, settings.capital, settings.riskPct, settings.horizonDays),
    [forecast, values.price, features.gold_atr14_pct, settings.capital, settings.riskPct, settings.horizonDays]);

  const pivots = useMemo(() => computePivots(market.candles), [market.candles]);  // bugün = gerçek takvim günü
  const pivotLadder = useMemo(
    () => buildLadder(pivots?.[settings.pivotPeriod] ?? null, settings.pivotMethod, (market.harem.satis ?? market.spot.price ?? 0)),
    [pivots, settings.pivotPeriod, settings.pivotMethod, market.harem.satis, market.spot.price]);

  const tech = useMemo(() => indicators(market.candles), [market.candles]);

  const historyEnd = market.history.length ? market.history[market.history.length - 1][0] : undefined;
  const dailyForecast = useMemo(
    () => buildDailyPath(model, forecast, settings.horizonDays, historyEnd),
    [forecast, settings.horizonDays, historyEnd]);

  /* Tablo, modelin yayınladığı ilk tahmine (model.latestDate) çapalıdır; o günkü girdilerle
     hesaplanır. Canlı girdilerle yeniden hesaplamak, geçmişi bugünün bilgisiyle tahmin etmek olurdu. */
  const originForecast = useMemo(() => predict(model, model.latest, model.latestPrice), []);

  const loan = useMemo(() => loanProjection(forecast, settings.horizonDays), [forecast, settings.horizonDays]);
  const costs = useMemo(() => loanCosts({
    amount: settings.loanAmount, ratePct: settings.loanRate, days: loan.days,
    currentFx: market.usdTry.satis ?? 0, futureFx: +settings.futureUsdTry || 0, scenarios: loan.scenarios,
  }), [loan, settings.loanAmount, settings.loanRate, market.usdTry.satis, settings.futureUsdTry]);

  /* Değer her render'da yeniden kurulduğu için her canlı tick tüm paneli
     yeniden çiziyordu (tick başına ~70 DOM mutasyonu ölçüldü). */
  return useMemo(() => ({
    ...market, ...settings, ...forecastModel,
    impacts, zones, pivots, pivotLadder, tech, dailyForecast, originForecast, loan, costs,
  }), [market, settings, forecastModel, impacts, zones, pivots, pivotLadder, tech,
       dailyForecast, originForecast, loan, costs]);
};

export type DashboardState = ReturnType<typeof useDashboardState>;

const DashboardContext = createContext<DashboardState | null>(null);

export const DashboardProvider = ({ children }: { children: ReactNode }) => (
  <DashboardContext.Provider value={useDashboardState()}>{children}</DashboardContext.Provider>
);

export const useDashboard = (): DashboardState => {
  const value = useContext(DashboardContext);
  if (!value) throw new Error('useDashboard yalnız DashboardProvider içinde kullanılabilir.');
  return value;
};
