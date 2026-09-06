import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react';
import { model } from '../../data/artifact';
import { IMPACT_LABELS } from '../../content/parameters';
import { computeImpacts } from '../../domain/model/impacts';
import { buildDailyPath } from '../../domain/model/predict';
import { loanCosts, loanProjection } from '../../domain/loan';
import type { Ladder } from '../../services/api/technical';
import { useForecastModel } from './useForecastModel';
import { useMarketData } from './useMarketData';
import { usePanelSettings } from './usePanelSettings';
import { useTechnical } from './useTechnical';

const useDashboardState = () => {
  const settings = usePanelSettings();
  /* Teknik paket önce: fiyat serisi, kapanış ve referans fiyat buradan türer. */
  const { technical, status: technicalStatus, refresh: refreshTechnical } = useTechnical(settings);
  const market = useMarketData(technical);
  /* Tahminin fiyat çapası teknik paketin referansı (GC=F, çerçevesiyle); Harem
     kotasyonu yalnız `PanelHeader`'da canlı fiyattır ve buraya hiç girmez. */
  const forecastBase = useMemo(() => {
    const ref = technical?.reference;
    return ref && ref.value != null ? { value: ref.value, frame: ref.frame } : null;
  }, [technical?.reference]);
  const forecastModel = useForecastModel(market.live, forecastBase, market.featuresDate);
  const { features, forecast } = forecastModel;

  /* Katkı kartı tahminle aynı fiyata bağlı (`/v1/predict` `base_price`), her
     tick'te değişen bir fiyata değil; iki "Referans fiyat" ayrışmasın. */
  const impacts = useMemo(
    () => computeImpacts(model, features, forecast.price, IMPACT_LABELS, forecast, settings.horizonDays),
    [features, forecast, settings.horizonDays]);

  /* Pivot merdiveni sunucudan gelir: fiyatı teknik paketin referansı, marjı
     ATR'den. Harem kotasyonu merdivene **girmez** (`LIVE_QUOTE_NOT_USED`). */
  const pivotHeadline = technical?.pivots?.headline ?? null;
  const pivotLadder: Ladder | null = pivotHeadline?.ladder ?? null;
  const pivotPeriodId = pivotHeadline?.periodId ?? null;
  const pivotSets = technical?.pivots?.sets ?? null;
  const reference = technical?.reference ?? null;
  const dailyChange = technical?.daily?.change ?? null;
  const sessionMeta = technical?.sessionMeta ?? null;
  const levels = technical?.levels ?? null;
  const momentumDaily = technical?.momentumDaily ?? null;
  const breakout = technical?.breakout ?? null;
  const trend = technical?.trend ?? null;
  const indicatorsBlock = technical?.indicators ?? null;

  const historyEnd = market.history.length ? market.history[market.history.length - 1][0] : undefined;
  const dailyForecast = useMemo(
    () => buildDailyPath(model, forecast, settings.horizonDays, forecast.originDate ?? historyEnd),
    [forecast, settings.horizonDays, historyEnd]);

  const loan = useMemo(() => loanProjection(forecast, settings.horizonDays), [forecast, settings.horizonDays]);
  const costs = useMemo(() => loanCosts({
    amount: settings.loanAmount, ratePct: settings.loanRate, days: loan.days,
    currentFx: market.usdTry.satis ?? 0, futureFx: +settings.futureUsdTry || 0, scenarios: loan.scenarios,
  }), [loan, settings.loanAmount, settings.loanRate, market.usdTry.satis, settings.futureUsdTry]);

  /* "Yenile" iki kaynağı birden tazeler; `...market`'in kendi `refresh`'i ezilir. */
  const marketRefresh = market.refresh;
  const refresh = useCallback(async () => { await Promise.all([marketRefresh(), refreshTechnical()]); }, [marketRefresh, refreshTechnical]);

  /* Değer her render'da yeniden kurulduğu için her canlı tick tüm paneli
     yeniden çiziyordu (tick başına ~70 DOM mutasyonu ölçüldü). */
  return useMemo(() => ({
    ...market, ...settings, ...forecastModel, refresh,
    technical, technicalStatus, reference, dailyChange, sessionMeta,
    pivotLadder, pivotHeadline, pivotPeriodId, pivotSets, levels, momentumDaily, breakout, trend,
    indicators: indicatorsBlock,
    impacts, dailyForecast, loan, costs,
  }), [market, settings, forecastModel, refresh, technical, technicalStatus, reference, dailyChange, sessionMeta,
       pivotLadder, pivotHeadline, pivotPeriodId, pivotSets, levels, momentumDaily, breakout, trend, indicatorsBlock,
       impacts, dailyForecast, loan, costs]);
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
