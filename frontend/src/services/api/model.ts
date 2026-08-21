import type { FeatureMap } from '../../domain/model/types';
import { MODEL_API } from '../config';
import { fetchJson, postJson } from '../http';

export type ApiForecast = { mean: number[]; err: number[]; version?: string };

export const requestForecast = async (price: number, features: FeatureMap): Promise<ApiForecast> => {
  const data = await fetchJson<{ mean: number[]; error: number[]; version?: string }>(
    `${MODEL_API}/v1/predict`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ price: +price, features }) },
  );
  return { mean: data.mean, err: data.error, version: data.version };
};

export type SnapshotBody = {
  model_price: number; display_price: number; features: FeatureMap;
  observed_at: string; source: string; display_source: string;
};

export const postSnapshot = (body: SnapshotBody) => postJson(`${MODEL_API}/v1/snapshots`, body);
