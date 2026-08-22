import { modelApi } from '../config';
import { fetchJson } from '../http';
import { CONFIDENT_WEIGHT } from './model';

export type ScorecardRow = {
  horizon: number;
  /** Ortalama mutlak hata (oran). */
  mae: number;
  /** Yön isabeti (oran). */
  direction: number;
  /** Sıfır getiri kuralına göre kazanılan beceri (oran). */
  skill: number;
  /** %80'lik hata bandı genişliği (oran). */
  error80: number;
  /** Hatanın 2 puanın altında kaldığı gün oranı. */
  within2pp: number;
  weight: number;
  confident: boolean;
  /** Ölçümün dayandığı katman dışı gün sayısı. */
  oofRows: number;
};

export type Scorecard = { version: string; rows: ScorecardRow[]; measuredDays: number };

const num = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

/**
 * Modelin karnesi servisten gelir.
 *
 * Bölüm daha önce tarayıcıdaki artefakttan üretiliyordu; o artefakt nötr
 * fallback'e dönüşünce (`fallback: true`) koşul hiçbir zaman sağlanmadı ve
 * kart **hiçbir dağıtımda görünmedi**. Sunucunun purge'lü walk-forward
 * ölçümleri hem gerçek hem çok daha geniş bir örnekleme dayanıyor.
 */
export const parseScorecard = (raw: unknown): Scorecard | null => {
  if (!raw || typeof raw !== 'object') return null;
  const data = raw as Record<string, unknown>;
  const metrics = data.metrics;
  if (!metrics || typeof metrics !== 'object') return null;

  const rows: ScorecardRow[] = [];
  Object.entries(metrics as Record<string, unknown>).forEach(([key, value]) => {
    const horizon = Number(key);
    if (!Number.isFinite(horizon) || !value || typeof value !== 'object') return;
    const m = value as Record<string, unknown>;
    const mae = num(m.mae), direction = num(m.direction), skill = num(m.skill_vs_zero);
    const error80 = num(m.error80), within2pp = num(m.within_2pp), oofRows = num(m.oof_rows);
    const weight = num(m.weight);
    if (mae == null || direction == null || skill == null
      || error80 == null || within2pp == null || oofRows == null || weight == null) return;
    rows.push({ horizon, mae, direction, skill, error80, within2pp, weight, oofRows,
      confident: weight >= CONFIDENT_WEIGHT });
  });

  if (!rows.length) return null;
  rows.sort((a, b) => a.horizon - b.horizon);
  return {
    version: typeof data.active_model === 'string' ? data.active_model : '',
    rows,
    measuredDays: Math.max(...rows.map(row => row.oofRows)),
  };
};

export const fetchScorecard = async (): Promise<Scorecard | null> =>
  parseScorecard(await fetchJson<unknown>(`${modelApi()}/v1/learning/metrics`));
