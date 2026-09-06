import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { model } from '../../data/artifact';
import { GROUPS } from '../../content/parameters';
import type { ReferenceFrame } from '../../content/technical';
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
  /** Keep the last successful result visible while a refresh is in flight. */
  hasForecast: boolean;
  /** Ufuk başına ağırlık; 0'a yakınsa model o vadede görüş bildirmiyor. */
  weights: number[];
  confident: boolean[];
  /** Eğitim aralığının dışına düşüp kırpılan girdiler. */
  clipped: string[];
  /** Donmuş olduğu için tahmine katılmayan girdiler. */
  neutralized: string[];
  /** Sunucunun geri yolladığı `base_price`'ın çerçevesi (istek anındaki referans); yanıt yokken `null`. */
  baseFrame: ReferenceFrame | null;
};

/** Tahminin dolara çevrildiği fiyat: teknik paketin referansı ve çerçevesi. */
export type ForecastBase = { value: number; frame: ReferenceFrame };

/**
 * Parametre formu + tahmin. Sunucu modeli ulaşılamazsa tarayıcıdaki
 * artefaktla hesaplanan tahmine düşer, panel boş kalmaz.
 *
 * `base` teknik paketin referans fiyatıdır (GC=F), Harem kotasyonu **değil**:
 * önceden her soket tick'i `price`'ı eziyor, sunucu onu `base_price` olarak
 * geri yolluyor ve hedef/bant/senaryo bölgeleri canlı spota çapalanıyordu.
 * Referans gelmeden istek atılmaz; yerine başka bir fiyat konmaz.
 */
export const useForecastModel = (live: FeatureMap, base: ForecastBase | null, sourceDate?: string | null): ForecastModel => {
  const [values, setValues] = useState<ParameterValues>(fieldDefaults);
  const [apiForecast, setApiForecast] = useState<ApiForecast | null>(null);
  const [apiFeatures, setApiFeatures] = useState<FeatureMap | null>(null);
  const [apiFrame, setApiFrame] = useState<ReferenceFrame | null>(null);
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

  const baseValue = base?.value ?? null;
  const baseFrame = base?.frame ?? null;
  useEffect(() => { if (baseValue != null) setField('price', baseValue); }, [baseValue]);

  const features = useMemo(() => computeFeatures(model, values, live), [values, live]);
  const signature = useMemo(() => JSON.stringify(features), [features]);
  const fallback = useMemo(() => predict(model, features, values.price), [features, values.price]);

  const latest = useRef({ features, frame: baseFrame });
  latest.current = { features, frame: baseFrame };

  useEffect(() => {
    const id = ++requestId.current;
    setModelStatus('loading');
    // Never present the bundled fallback feature vector as current input while
    // the canonical endpoint has not yet supplied its timestamp, and never send
    // a substitute price while the technical reference is missing.
    if (!sourceDate || baseValue == null) return;
    const timer = setTimeout(() => {
      const input = latest.current;
      requestForecast(baseValue, input.features, sourceDate)
        .then(result => { if (id === requestId.current) { setApiFeatures(input.features); setApiFrame(input.frame); setApiForecast(result); setModelStatus('live'); } })
        .catch(() => { if (id === requestId.current) { setApiForecast(null); setModelStatus('fallback'); } });
    }, PREDICT_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [signature, refreshKey, sourceDate, baseValue]);

  const forecast = useMemo<Forecast>(
    () => (apiForecast ? { ...apiForecast, features: apiFeatures ?? features, price: apiForecast.basePrice ?? +values.price } : fallback),
    [apiForecast, apiFeatures, fallback, features, values.price]);

  const refreshForecast = useCallback(() => setRefreshKey(key => key + 1), []);
  return useMemo(() => ({
    values, setField, refreshForecast,
    features: forecast.features, forecast, version: apiForecast?.version, modelStatus, hasForecast: apiForecast !== null,
    weights: apiForecast?.weights ?? forecast.horizons.map(() => 0),
    confident: apiForecast?.confident ?? forecast.horizons.map(() => false),
    clipped: apiForecast?.clipped ?? [],
    neutralized: apiForecast?.neutralized ?? [],
    baseFrame: apiForecast ? apiFrame : null,
  }), [values, features, forecast, apiForecast, apiFrame, modelStatus, refreshForecast]);
};
