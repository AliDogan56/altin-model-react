import type { SeriesPoint } from '../../lib/series';
import type { FeatureMap } from '../model/types';

export const FRED_IDS = [
  'DGS10', 'DGS2', 'DFII10', 'DTWEXBGS', 'DCOILWTICO', 'VIXCLS', 'FEDFUNDS',
  'CPIAUCSL', 'CPILFESL', 'PPIACO', 'PCEPI', 'UNRATE', 'PAYEMS', 'RSAFS',
] as const;

/** Doğrudan seviye olarak modele giden seriler. */
const LEVELS = ['DGS10', 'DGS2', 'DFII10', 'DTWEXBGS', 'DCOILWTICO', 'VIXCLS', 'FEDFUNDS', 'UNRATE'] as const;

export const macroFeatures = (series: Record<string, SeriesPoint[]>): FeatureMap => {
  const last = (id: string) => series[id].at(-1)!.value;
  const back = (id: string, n: number) => series[id].at(-1 - n)!.value;
  const chg = (id: string, n: number, ratio = false) =>
    ratio ? last(id) / back(id, n) - 1 : last(id) - back(id, n);
  const yoy = (id: string) => (last(id) / back(id, 12) - 1) * 100;

  const f: FeatureMap = {};
  LEVELS.forEach(id => { f[id] = last(id); });
  return Object.assign(f, {
    CPIAUCSL_yoy_pct: yoy('CPIAUCSL'),
    CPILFESL_yoy_pct: yoy('CPILFESL'),
    PPIACO_yoy_pct: yoy('PPIACO'),
    PCEPI_yoy_pct: yoy('PCEPI'),
    PAYEMS_change_k: chg('PAYEMS', 1),
    RSAFS_mom_pct: chg('RSAFS', 1, true) * 100,
    real_yield_change_5d: chg('DFII10', 5),
    dollar_return_5d: chg('DTWEXBGS', 5, true),
    oil_return_5d: chg('DCOILWTICO', 5, true),
    vix_change_5d: chg('VIXCLS', 5),
  });
};
