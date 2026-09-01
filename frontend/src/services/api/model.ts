import type { FeatureMap } from '../../domain/model/types';
import { modelApi } from '../config';
import { fetchJson } from '../http';

export type ApiForecast = {
  horizons: number[]; mean: number[]; err: number[]; version?: string;
  /** Ufkun ağırlığı; 0'a yakınsa ağın katkısı kısılmıştır. */
  weights: number[];
  /** Ağırlığı eşiğin altındaki ufuk "tahmin" değil "görüş yok" olarak sunulmalı. */
  confident: boolean[];
  /** Eğitim aralığının dışına düşüp kırpılan girdiler. */
  clipped: string[];
  /** Güncel bilgi taşımadığı için hesaba katılmayan girdiler. */
  neutralized: string[];
  featureEffects?: Record<string, FeatureMap>;
};

export type LatestFeatures = { date: string; price: number; features: FeatureMap };

/** Tahmin girdilerinin tek kaynağı. Tarayıcı bunları kendi hesapladığında
 *  19 alanın 10'u eğitim setinden farklı çıkıyordu (makro geri bakışları
 *  gözlem sayısına ve yanlış çapa tarihine göre yapılıyordu). */
export const fetchLatestFeatures = () =>
  fetchJson<LatestFeatures>(`${modelApi()}/v1/features/latest`);

const numbers = (value: unknown, length?: number): number[] | null => {
  if (!Array.isArray(value) || value.length === 0) return null;
  if (length != null && value.length !== length) return null;
  return value.every(item => typeof item === 'number' && Number.isFinite(item)) ? value as number[] : null;
};

/**
 * Sunucu yanıtını arayüze sokmadan önce doğrular.
 *
 * Doğrulama yokken eksik `horizons` alanı `forecast.horizons.indexOf(...)`
 * üzerinden fırlıyor ve ErrorBoundary de olmadığı için **tüm sayfa beyaza
 * düşüyordu**. Artık bozuk yanıt `null` döner, çağıran fallback'e geçer.
 */
export const parseForecast = (raw: unknown): ApiForecast | null => {
  if (!raw || typeof raw !== 'object') return null;
  const data = raw as Record<string, unknown>;

  const horizons = numbers(data.horizons);
  if (!horizons) return null;
  const mean = numbers(data.mean, horizons.length);
  const err = numbers(data.error, horizons.length);
  if (!mean || !err) return null;

  const weights = numbers(data.weights, horizons.length) ?? horizons.map(() => 1);
  const confident = Array.isArray(data.confident) && data.confident.length === horizons.length
    ? data.confident.map(Boolean)
    : weights.map(weight => weight >= CONFIDENT_WEIGHT);
  const strings = (value: unknown): string[] => (Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string') : []);
  const clipped = strings(data.clipped_features);
  const neutralized = strings(data.neutralized_features);

  return {
    horizons, mean, err, weights, confident, clipped, neutralized,
    version: typeof data.version === 'string' ? data.version : undefined,
    featureEffects: (data.feature_effects as Record<string, FeatureMap> | undefined) ?? undefined,
  };
};

/** Servisin `confident` eşiğiyle aynı; yanıt bu alanı taşımazsa buradan türetilir. */
export const CONFIDENT_WEIGHT = 0.2;

export const requestForecast = async (price: number, features: FeatureMap): Promise<ApiForecast> => {
  const forecast = parseForecast(await fetchJson<unknown>(
    `${modelApi()}/v1/predict`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ price: +price, features }) },
  ));
  if (!forecast) throw new Error('Model servisi beklenen tahmin şemasını döndürmedi');
  return forecast;
};
