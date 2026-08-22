import type { ImpactLabel } from '../../content/parameters';
import { resolveHorizon } from './horizon';
import { predict } from './predict';
import type { FeatureMap, Forecast, ModelArtifact } from './types';

/** Girdinin bugünkü değeri kendi geçmişine göre ne kadar sıra dışı. */
export type Unusualness = 'normal' | 'high' | 'extreme';

export type Impact = {
  key: string; label: string; hint: string;
  /** Tahmine etkisi (oran). */
  value: number;
  /** Aynı etkinin dolar karşılığı — okuyucu için tek somut birim. */
  usd: number;
  z: number;
  unusualness: Unusualness;
  /** En büyük etkiye göre çubuk payı (0–1). */
  share: number;
};

export type Impacts = {
  up: Impact[]; down: Impact[];
  /** Yukarı iten ve aşağı çeken etkilerin dolar toplamı. */
  upUsd: number; downUsd: number; netUsd: number;
  /** Servis tahmini (oran) ve dolar karşılığı. */
  here: number; hereUsd: number;
  price: number; horizon: number; live: boolean;
};

/** Yuvarlandığında sıfır dolar görünen etkiler listeye alınmaz. */
const MIN_VISIBLE_USD = 1;

const unusualness = (z: number): Unusualness =>
  Math.abs(z) >= 1.5 ? 'extreme' : Math.abs(z) >= 0.6 ? 'high' : 'normal';

/**
 * Her satır tek bir soruyu yanıtlar: bu girdi bugünkü değerinde olmasaydı, yani
 * kendi uzun dönem ortalamasında olsaydı, tahmin ne kadar değişirdi.
 *
 * Kart eskiden 19 girdinin yalnız 14'ünü listeliyordu; en büyük etki bile
 * gizli kalabiliyordu ve gösterilen sayılar hiçbir toplama oturmuyordu.
 * Artık tamamı yukarı itenler / aşağı çekenler olarak ayrılır ve dolar
 * cinsinden verilir.
 */
export const computeImpacts = (
  model: ModelArtifact, features: FeatureMap, price: number, labels: Record<string, ImpactLabel>,
  forecast?: Forecast, horizon = 30,
): Impacts => {
  const resolved = resolveHorizon(model.horizons, horizon);
  const at = (f: FeatureMap) => predict(model, f, price).mean[resolved.index];
  const here = at(features);
  const serverHorizon = forecast ? resolveHorizon(forecast.horizons, horizon) : null;
  const serverEffects = forecast?.featureEffects?.[String(serverHorizon?.horizon ?? horizon)];

  const rows = model.features.map(key => {
    const index = model.features.indexOf(key);
    const changed: FeatureMap = { ...features, [key]: model.xMean[index] };
    const value = serverEffects?.[key] ?? here - at(changed);
    const z = model.xStd[index] ? (features[key] - model.xMean[index]) / model.xStd[index] : 0;
    const known = labels[key];
    return {
      key, value, z, unusualness: unusualness(z), usd: value * price, share: 0,
      label: known?.label ?? key, hint: known?.hint ?? '',
    };
  }).filter(row => Number.isFinite(row.value));

  const peak = Math.max(...rows.map(r => Math.abs(r.value)), 1e-9);
  const withShare = rows.map(r => ({ ...r, share: Math.abs(r.value) / peak }));
  const bySize = (a: Impact, b: Impact) => Math.abs(b.value) - Math.abs(a.value);

  // Toplamlar tüm girdilerden; listeler yalnız görünür büyüklükte olanlardan.
  // "−$0" yazan satır okuyucuya hiçbir şey söylemiyor, sadece listeyi uzatıyor.
  const upUsd = withShare.filter(r => r.value > 0).reduce((sum, r) => sum + r.usd, 0);
  const downUsd = withShare.filter(r => r.value < 0).reduce((sum, r) => sum + r.usd, 0);
  const visible = withShare.filter(r => Math.abs(r.usd) >= MIN_VISIBLE_USD);
  const up = visible.filter(r => r.value > 0).sort(bySize);
  const down = visible.filter(r => r.value < 0).sort(bySize);

  const liveHere = forecast && serverHorizon ? forecast.mean[serverHorizon.index] : here;

  return {
    up, down, upUsd, downUsd, netUsd: upUsd + downUsd,
    here: liveHere, hereUsd: liveHere * price, price,
    live: Boolean(serverEffects), horizon: serverHorizon?.horizon ?? resolved.horizon,
  };
};
