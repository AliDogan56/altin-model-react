import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { model } from '../../data/artifact';
import { GROUPS } from '../../content/parameters';
import { PCT_FIELDS, computeFeatures } from '../../domain/model/features';
import { predict } from '../../domain/model/predict';
import type { FeatureMap, Forecast } from '../../domain/model/types';
import { requestForecast, type ApiForecast } from '../../services/api/model';

const PREDICT_DEBOUNCE_MS = 700;

export type ParameterValues = Record<string, number>;

const fieldDefaults = (): ParameterValues => Object.fromEntries(
  GROUPS.flatMap(([, items]) => items).map(([id]) =>
    [id, id === 'price' ? model.latestPrice : model.latest[id] * (PCT_FIELDS.has(id) ? 100 : 1)]),
);

export type ForecastModel = {
  values: ParameterValues;
  setField: (id: string, value: number) => void;
  refreshForecast: () => void;
  features: FeatureMap;
  forecast: Forecast;
  version?: string;
  modelStatus: 'loading' | 'live' | 'fallback';
  /** Ufuk başına ağırlık; 0'a yakınsa model o vadede görüş bildirmiyor. */
  weights: number[];
  confident: boolean[];
  /** Eğitim aralığının dışına düşüp kırpılan girdiler. */
  clipped: string[];
  /** Donmuş olduğu için tahmine katılmayan girdiler. */
  neutralized: string[];
};

/** Parametre formu + tahmin. Sunucu modeli ulaşılamazsa tarayıcıdaki
 *  artefaktla hesaplanan tahmine düşer, panel boş kalmaz. */
export const useForecastModel = (live: FeatureMap, lastClose: number | null, spotPrice: number): ForecastModel => {
  const [values, setValues] = useState<ParameterValues>(fieldDefaults);
  const [apiForecast, setApiForecast] = useState<ApiForecast | null>(null);
  const [modelStatus, setModelStatus] = useState<'loading' | 'live' | 'fallback'>('loading');
  const [refreshKey, setRefreshKey] = useState(0);
  const requestId = useRef(0);
  const setField = (id: string, value: number) => setValues(v => ({ ...v, [id]: value }));
  // Canlı çekim geldiğinde forma yazılır; kullanıcı sonrasında serbestçe değiştirebilir.
  useEffect(() => {
    if (!Object.keys(live).length) return;
    setValues(v => {
      const next = { ...v };
      GROUPS.flatMap(([, items]) => items).forEach(([id]) => {
        if (live[id] != null) next[id] = live[id] * (PCT_FIELDS.has(id) ? 100 : 1);
      });
      return next;
    });
  }, [live]);

  useEffect(() => { if (lastClose != null) setField('price', lastClose); }, [lastClose]);
  useEffect(() => { if (Number.isFinite(spotPrice)) setField('price', spotPrice); }, [spotPrice]);

  const features = useMemo(() => computeFeatures(model, values, live), [values, live]);
  const signature = useMemo(() => JSON.stringify(features), [features]);
  const fallback = useMemo(() => predict(model, features, values.price), [features, values.price]);

  const latest = useRef({ features, price: values.price });
  latest.current = { features, price: values.price };

  useEffect(() => {
    const id = ++requestId.current;
    setApiForecast(null);
    setModelStatus('loading');
    const timer = setTimeout(() => {
      requestForecast(latest.current.price, latest.current.features)
        .then(result => { if (id === requestId.current) { setApiForecast(result); setModelStatus('live'); } })
        .catch(() => { if (id === requestId.current) setModelStatus('fallback'); });
    }, PREDICT_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [signature, refreshKey]);

  const forecast = useMemo<Forecast>(
    () => (apiForecast ? { ...apiForecast, features, price: +values.price } : fallback),
    [apiForecast, fallback, features, values.price]);

  const refreshForecast = useCallback(() => setRefreshKey(key => key + 1), []);
  return useMemo(() => ({
    values, setField, refreshForecast,
    features, forecast, version: apiForecast?.version, modelStatus,
    weights: apiForecast?.weights ?? forecast.horizons.map(() => 0),
    confident: apiForecast?.confident ?? forecast.horizons.map(() => false),
    clipped: apiForecast?.clipped ?? [],
    neutralized: apiForecast?.neutralized ?? [],
  }), [values, features, forecast, apiForecast, modelStatus, refreshForecast]);
};
