import { marketApi } from '../config';
import { fetchJson } from '../http';

export type Direction = 'UP' | 'DOWN' | 'NEUTRAL';
/** Kırılım gücü etiketi; hesabı `domain/momentum/breakPotential.ts` yapar. */
export type BreakStrength = 'WEAK' | 'MEDIUM' | 'STRONG';
export type MomentumTrend = 'STRENGTHENING' | 'WEAKENING' | 'STABLE';

/**
 * Yalnız **momentum büyüklükleri**. Servis destek/direnç ve kırılım hedefi de
 * döner ama arayüz onları kullanmaz: seviyeler panelin pivot merdiveninden
 * gelir, yoksa aynı ekranda iki farklı "ilk direnç" görünüyordu.
 */
export type Momentum = {
  asOf: string;
  price: number;
  direction: Direction;
  /** 0–100, o seansın oynaklığına göre normalize. */
  strength: number;
  trend: MomentumTrend;
  components: Record<string, number>;
  session: {
    bars: number;
    remainingBars: number;
    volatilityPct: number;
    expectedMove: number;
    hasVolume: boolean;
  };
};

const num = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

const DIRECTIONS: Direction[] = ['UP', 'DOWN', 'NEUTRAL'];
const TRENDS: MomentumTrend[] = ['STRENGTHENING', 'WEAKENING', 'STABLE'];

/**
 * Sunucu yanıtını arayüze sokmadan doğrular. Bozuk şema `null` döner ve bölüm
 * hiç görünmez — yarım bir momentum kartı yanıltıcı olurdu.
 */
export const parseMomentum = (raw: unknown): Momentum | null => {
  if (!raw || typeof raw !== 'object') return null;
  const data = raw as Record<string, unknown>;

  const price = num(data.price); const strength = num(data.strength);
  const direction = data.direction as Direction;
  const trend = data.trend as MomentumTrend;
  if (price === null || strength === null) return null;
  if (!DIRECTIONS.includes(direction) || !TRENDS.includes(trend)) return null;

  const session = (data.session ?? {}) as Record<string, unknown>;
  const volatility = num(session.volatility_pct);
  if (volatility === null) return null;

  const components: Record<string, number> = {};
  for (const [key, value] of Object.entries((data.components ?? {}) as Record<string, unknown>)) {
    const parsed = num(value);
    if (parsed !== null) components[key] = parsed;
  }

  return {
    asOf: typeof data.as_of === 'string' ? data.as_of : '',
    price, direction, strength: Math.max(0, Math.min(100, Math.round(strength))), trend,
    components,
    session: {
      bars: num(session.bars) ?? 0,
      remainingBars: num(session.remaining_bars) ?? 0,
      volatilityPct: volatility,
      expectedMove: num(session.expected_move) ?? 0,
      hasVolume: session.has_volume === true,
    },
  };
};

export const fetchMomentum = async (): Promise<Momentum | null> =>
  parseMomentum(await fetchJson<unknown>(`${marketApi()}/v1/market/xau/momentum`));
