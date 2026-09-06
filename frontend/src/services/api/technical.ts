import { marketApi } from '../config';
import { fetchJson } from '../http';
import { parseMomentum, type Direction, type Momentum, type MomentumTrend } from './momentum';

/*
 * `GET /v1/market/xau/technical` — teknik analizin tamamı sunucuda hesaplanır;
 * bu dosya yalnız snake_case yanıtı doğrulayıp camelCase tiplere çevirir.
 *
 * İki kural:
 * - Her blok **bağımsız** doğrulanır. Bozuk ya da eksik blok `null` olur ve
 *   yalnız o kart gizlenir; sayfa düşmez. Yalnız `status` ve `reference`
 *   zorunludur — onlarsız hiçbir kart neyi referans aldığını söyleyemez.
 * - Enum alanları (yön, güç etiketi, gösterge/kanal/uyum durumu, rol, çerçeve)
 *   **bilinen listeyle** sınırlıdır; bilinmeyen değer bloğu `null` yapar.
 *   Sunucu yeni bir değer eklerse kart sessizce yanlış bir şey yazmak yerine
 *   kaybolur — ileriye dönük katılık, arayüz sözlüğü güncellenince açılır.
 */

export const BLOCKS = ['daily', 'session', 'indicators', 'pivots', 'levels', 'momentum_daily', 'breakout', 'trend'] as const;
export const DIRECTIONS = ['UP', 'DOWN', 'NEUTRAL'] as const;
export const MOMENTUM_TRENDS = ['STRENGTHENING', 'WEAKENING', 'STABLE'] as const;
/** Bölge, günlük momentum ve kırılım gücü etiketi (seans bloğunun `MEDIUM`'undan farklı). */
export const STRENGTH_LABELS = ['WEAK', 'MODERATE', 'STRONG'] as const;
export const INDICATOR_STATES = ['OVERBOUGHT', 'OVERSOLD', 'NEUTRAL', 'ABOVE_SIGNAL', 'BELOW_SIGNAL', 'TRENDING', 'WEAK_TREND',
  'HIGH_VOLATILITY', 'LOW_VOLATILITY', 'NORMAL_VOLATILITY', 'POSITIVE', 'NEGATIVE', 'ABOVE', 'BELOW'] as const;
export const CHANNEL_STATES = ['BELOW_2SIGMA', 'BELOW_1SIGMA', 'NEAR_TREND', 'ABOVE_1SIGMA', 'ABOVE_2SIGMA'] as const;
export const FIT_STATES = ['GOOD', 'MODERATE', 'WEAK'] as const;
export const TREND_DIRECTIONS = ['UP', 'DOWN', 'FLAT'] as const;
export const TIMEFRAMES = ['DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'SEMIANNUAL'] as const;
export const LADDER_ROLES = ['NEAREST_UP', 'NEAREST_DOWN', 'TESTING'] as const;
export const LADDER_OUTSIDE = ['ABOVE_ALL', 'BELOW_ALL'] as const;
export const PIVOT_POSITIONS = ['ABOVE', 'BELOW', 'AT'] as const;
export const REFERENCE_FRAMES = ['intraday_close', 'daily_close'] as const;
export const PIVOT_METHODS = ['CLASSIC', 'FIBONACCI', 'CAMARILLA'] as const;
export const PIVOT_PERIODS = ['DAILY', 'WEEKLY', 'MONTHLY'] as const;
export const PIVOT_COMPLETIONS = ['LAST_BAR_PRESENT', 'SUCCEEDED_BY_LATER_BAR', 'GRACE_ELAPSED', 'NONE'] as const;
export const ZONE_KINDS = ['SUPPORT', 'RESISTANCE'] as const;
export const BREAKOUT_SIDES = ['up', 'down'] as const;
export const EXPECTED_MOVE_FRAMES = ['session_remaining', 'next_daily_bar'] as const;
export const MARKET_STATES = ['OPEN', 'CLOSED'] as const;

export type Block = typeof BLOCKS[number];
export type StrengthLabel = typeof STRENGTH_LABELS[number];
export type IndicatorState = typeof INDICATOR_STATES[number];
export type ChannelState = typeof CHANNEL_STATES[number];
export type FitState = typeof FIT_STATES[number];
export type TrendDirection = typeof TREND_DIRECTIONS[number];
export type Timeframe = typeof TIMEFRAMES[number];
export type LadderRole = typeof LADDER_ROLES[number];
export type LadderOutside = typeof LADDER_OUTSIDE[number];
export type PivotPosition = typeof PIVOT_POSITIONS[number];
export type ReferenceFrame = typeof REFERENCE_FRAMES[number];
export type PivotMethod = typeof PIVOT_METHODS[number];
export type PivotPeriod = typeof PIVOT_PERIODS[number];
export type PivotCompletion = typeof PIVOT_COMPLETIONS[number];
export type ZoneKind = typeof ZONE_KINDS[number];
export type BreakoutSideKey = typeof BREAKOUT_SIDES[number];
export type ExpectedMoveFrame = typeof EXPECTED_MOVE_FRAMES[number];
export type MarketState = typeof MARKET_STATES[number];

/** Tüm blokların ölçtüğü fiyat: gün içi son mum ya da günlük kapanış. */
export type Reference = {
  value: number | null; frame: ReferenceFrame; instrument: string | null; asOf: string | null;
  dailyDate: string | null; dailyClose: number | null; status: string; note: string | null;
  source: { daily: string | null; dailyPriceSource: string | null; dailyFallback: boolean; intraday: string | null };
};
export type DailyChange = { date: string; previousDate: string; close: number; previousClose: number; usd: number; pct: number | null };
/** `prevClose` gövdenin diğer ucu (açılış yok); serinin ilk mumunda `null`. */
export type DailyCandle = { date: string; high: number; low: number; close: number; prevClose: number | null };
export type DailyQuality = {
  rows: number; rejected: number; duplicates: number; zeroRange: number; lastIsForming: boolean;
  firstDate: string | null; lastDate: string | null; intradayBars: number;
};
export type Daily = { status: string; bodyDefinition: string; change: DailyChange | null; quality: DailyQuality; candles: DailyCandle[] };
export type SessionMeta = {
  status: string; frame: string | null; instrument: string | null; stale: boolean;
  marketState: MarketState | null; sessionDate: string | null; error: string | null;
};
export type IndicatorRow = { key: string; value: number | null; state: IndicatorState | null; extra: Record<string, number | null> };
export type MovingAverageRow = { period: number; sma: number | null; ema: number | null; priceAboveSma: boolean | null };
export type Indicators = { status: string; date: string | null; bars: number; atr: number | null; rows: IndicatorRow[]; movingAverages: MovingAverageRow[] };

export type PivotLevel = { name: string; value: number };
export type PivotPeriodInfo = {
  period: PivotPeriod; periodId: string; start: string | null; end: string | null; bars: number;
  high: number | null; low: number | null; close: number | null; completion: PivotCompletion; status: string; missingBarFor: string | null;
};
export type PivotSet = PivotPeriodInfo & { classic: PivotLevel[]; fibonacci: PivotLevel[]; camarilla: PivotLevel[] };
/** Eski tarayıcı merdiveninin alan adları korundu (`name, value, distance, above`); hepsi artık sunucudan. */
export type LadderItem = {
  name: string; value: number; distance: number; distanceUsd: number; distanceAtr: number | null; above: boolean;
  role: LadderRole | null; band: [number, number]; zoneId: string | null;
};
export type Ladder = {
  price: number; marginUsd: number; items: LadderItem[]; insertAt: number; nearestUp: string | null; nearestDown: string | null;
  testing: string[]; outside: LadderOutside | null; positionVsPivot: PivotPosition | null; frame: ReferenceFrame;
};
export type PivotHeadline = PivotPeriodInfo & { method: PivotMethod; levels: PivotLevel[]; ladder: Ladder };
export type Pivots = {
  status: string; pivotMethod: PivotMethod; pivotPeriod: PivotPeriod; minCandles: number;
  headline: PivotHeadline; sets: Record<'daily' | 'weekly' | 'monthly', PivotSet | null>;
};

export type ZoneSource = { price: number; sourceType: string; label: string; weight: number; date: string | null; confirmed: boolean };
export type Zone = {
  id: string; mid: number; low: number; high: number; kind: ZoneKind; strength: number; label: StrengthLabel; name: string;
  sources: ZoneSource[]; sourceTypes: string[]; touches: number; rejections: number; breaks: number; pending: number;
  lastTouch: string | null; lastBreak: string | null; confirmed: boolean; components: Record<string, number>;
  distancePct: number; distanceUsd: number; distanceAtr: number | null; distanceSigma: number | null; testing: boolean;
};
export type LevelsNearest = { nearestSupport: string | null; nextSupport: string | null; nearestResistance: string | null; nextResistance: string | null };
export type Levels = LevelsNearest & {
  status: string; asOf: string | null; atr: number | null; sigma: number | null; marginUsd: number | null; minStrength: number | null;
  zones: Zone[]; testing: string[]; sideStatus: { support: string; resistance: string };
};
export type MomentumDaily = {
  status: string; date: string | null; score: number; direction: Direction; strength: StrengthLabel; trend: MomentumTrend;
  agreement: number; z: number; delta: number; acceleration: number; note: string | null;
  components: Record<string, number>; weights: Record<string, number>; zScale: number | null; history: number[];
  sigma: number | null; atr: number | null;
};
export type BreakoutTarget = { zoneId: string | null; name: string; value: number; zoneStrength: number | null; fallback: boolean };
export type BreakoutSide = {
  status: string; target: BreakoutTarget | null; distanceUsd: number | null; distancePct: number | null; distanceAtr: number | null;
  distanceSigma: number | null; reach: number | null; push: number | null; damping: number | null; components: Record<string, number>;
  strength: number | null; label: StrengthLabel | null; note: string | null;
};
export type Breakout = {
  status: string; note: string | null; headline: BreakoutSideKey | null; sessionDirection: Direction | null; sessionStrength: number | null;
  dailyDirection: Direction | null; dailyScore: number | null; expectedMove: number | null; expectedMoveFrame: ExpectedMoveFrame | null;
  expectedMovePct: number | null; weights: { session: number; daily: number }; up: BreakoutSide; down: BreakoutSide;
};
export type TrendFit = {
  n: number; intercept: number; slope: number; slopePct: number; first: number; last: number; r2: number; changePct: number;
  direction: TrendDirection; sigma: number; lastZ: number;
};
/** `wickHigh/Low` aralığı kapanış ve önceki kapanışı da kapsayacak şekilde genişletilmiş fitil. */
export type TrendRow = {
  date: string; high: number; low: number; close: number; prevClose: number | null; wickHigh: number; wickLow: number;
  fit: number | null; b1: [number, number] | null; b2: [number, number] | null; complete: boolean;
};
export type TrendRange = {
  id: string; timeframe: Timeframe; bars: number; candles: boolean; status: string; lastBucketForming: boolean;
  fit: TrendFit | null; realizedPct: number | null; channelState: ChannelState | null; fitState: FitState | null; rows: TrendRow[];
};
export type Trend = { status: string; ranges: Record<string, TrendRange> };

export type Technical = {
  version: string; generatedAt: string; configHash: string; status: Record<Block, string>; reference: Reference;
  daily: Daily | null; session: Momentum | null; sessionMeta: SessionMeta; indicators: Indicators | null; pivots: Pivots | null;
  levels: Levels | null; momentumDaily: MomentumDaily | null; breakout: Breakout | null; trend: Trend | null;
};

/* --- doğrulama yardımcıları --------------------------------------------------
 * Blok içinde eksik/bozuk alan `Invalid` fırlatır, `block()` bunu `null`'a
 * çevirir. İç içe onlarca alanı tek tek `if (...) return null` ile taramak
 * dosyayı üç katına çıkarıyordu; `Invalid` dışındaki hatalar yine yükselir. */
class Invalid extends Error {}
const need = <T>(value: T | null | undefined): T => { if (value == null) throw new Invalid(); return value; };
const block = <T>(fn: () => T): T | null => { try { return fn(); } catch (error) { if (error instanceof Invalid) return null; throw error; } };
const num = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
const str = (value: unknown): string | null => typeof value === 'string' ? value : null;
const bool = (value: unknown): boolean | null => typeof value === 'boolean' ? value : null;
const obj = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
const arr = (value: unknown): unknown[] => Array.isArray(value) ? value : [];
const strings = (value: unknown): string[] => arr(value).filter((item): item is string => typeof item === 'string');
const pair = (value: unknown): [number, number] | null =>
  Array.isArray(value) && value.length === 2 && num(value[0]) !== null && num(value[1]) !== null ? [value[0], value[1]] : null;
const numMap = (value: unknown): Record<string, number> => {
  const out: Record<string, number> = {};
  for (const [key, item] of Object.entries(obj(value) ?? {})) { const parsed = num(item); if (parsed !== null) out[key] = parsed; }
  return out;
};
const enumOf = <T extends string>(allowed: readonly T[], value: unknown): T => {
  if (!allowed.includes(value as T)) throw new Invalid(); return value as T;
};
/** `null`/eksik kabul edilir; **bilinmeyen** değer bloğu düşürür (yukarıdaki kural). */
const enumOrNull = <T extends string>(allowed: readonly T[], value: unknown): T | null => value == null ? null : enumOf(allowed, value);
const statusOf = (d: Record<string, unknown>): string => str(d.status) ?? 'UNKNOWN';

/* --- bloklar ----------------------------------------------------------------- */
const parseReference = (raw: unknown): Reference | null => block(() => {
  const d = need(obj(raw)); const source = obj(d.source) ?? {};
  return {
    value: d.value == null ? null : need(num(d.value)), frame: enumOf(REFERENCE_FRAMES, d.frame), instrument: str(d.instrument),
    asOf: str(d.as_of), dailyDate: str(d.daily_date), dailyClose: num(d.daily_close), status: statusOf(d), note: str(d.note),
    source: { daily: str(source.daily), dailyPriceSource: str(source.daily_price_source),
      dailyFallback: source.daily_fallback === true, intraday: str(source.intraday) },
  };
});

const parseCandle = (row: unknown): DailyCandle => {
  const r = need(Array.isArray(row) && row.length >= 4 ? row : null);
  return { date: need(str(r[0])), high: need(num(r[1])), low: need(num(r[2])), close: need(num(r[3])), prevClose: r[4] == null ? null : need(num(r[4])) };
};
const parseDaily = (raw: unknown): Daily | null => block(() => {
  const d = need(obj(raw)); const q = obj(d.quality) ?? {};
  const candles = arr(d.candles).map(parseCandle);
  if (!candles.length) throw new Invalid();
  const c = d.change == null ? null : need(obj(d.change));
  return {
    status: statusOf(d), bodyDefinition: str(d.body_definition) ?? 'prev_close_to_close', candles,
    change: c && { date: need(str(c.date)), previousDate: need(str(c.previous_date)), close: need(num(c.close)),
      previousClose: need(num(c.previous_close)), usd: need(num(c.usd)), pct: num(c.pct) },
    quality: { rows: num(q.rows) ?? candles.length, rejected: num(q.rejected) ?? 0, duplicates: num(q.duplicates) ?? 0,
      zeroRange: num(q.zero_range) ?? 0, lastIsForming: q.last_is_forming === true, firstDate: str(q.first_date),
      lastDate: str(q.last_date), intradayBars: num(q.intraday_bars) ?? 0 },
  };
});

/** Seans bloğu ayakta olmasa da (gün içi veri yok) meta okunur: kart "neden yok"u yazabilsin. */
const parseSessionMeta = (raw: unknown, fallbackStatus: string): SessionMeta => {
  const d = obj(raw) ?? {};
  return { status: str(d.status) ?? fallbackStatus, frame: str(d.frame), instrument: str(d.instrument), stale: d.stale === true,
    marketState: MARKET_STATES.includes(d.market_state as MarketState) ? d.market_state as MarketState : null,
    sessionDate: str(d.session_date), error: str(d.error) };
};

const parseIndicators = (raw: unknown): Indicators | null => block(() => {
  const d = need(obj(raw));
  const rows = arr(d.rows).map((row): IndicatorRow => {
    const r = need(obj(row)); const extra: Record<string, number | null> = {};
    for (const [key, value] of Object.entries(obj(r.extra) ?? {})) extra[key] = num(value);
    return { key: need(str(r.key)), value: num(r.value), state: enumOrNull(INDICATOR_STATES, r.state), extra };
  });
  if (!rows.length) throw new Invalid();
  const movingAverages = arr(d.moving_averages).map((row): MovingAverageRow => {
    const r = need(obj(row));
    return { period: need(num(r.period)), sma: num(r.sma), ema: num(r.ema), priceAboveSma: bool(r.price_above_sma) };
  });
  return { status: statusOf(d), date: str(d.date), bars: num(d.bars) ?? 0, atr: num(d.atr), rows, movingAverages };
});

const parsePivotLevels = (raw: unknown): PivotLevel[] => need(Array.isArray(raw) ? raw : null).map(item => {
  const r = need(Array.isArray(item) && item.length === 2 ? item : null);
  return { name: need(str(r[0])), value: need(num(r[1])) };
});
const parsePeriodInfo = (d: Record<string, unknown>): PivotPeriodInfo => ({
  period: enumOf(PIVOT_PERIODS, d.period), periodId: need(str(d.period_id)), start: str(d.start), end: str(d.end),
  bars: num(d.bars) ?? 0, high: num(d.high), low: num(d.low), close: num(d.close),
  completion: enumOf(PIVOT_COMPLETIONS, d.completion), status: statusOf(d), missingBarFor: str(d.missing_bar_for),
});
const parseLadder = (raw: unknown): Ladder => {
  const d = need(obj(raw));
  const items = arr(d.items).map((item): LadderItem => {
    const r = need(obj(item));
    return { name: need(str(r.name)), value: need(num(r.value)), distance: need(num(r.distance)), distanceUsd: need(num(r.distance_usd)),
      distanceAtr: num(r.distance_atr), above: need(bool(r.above)), role: enumOrNull(LADDER_ROLES, r.role), band: need(pair(r.band)),
      zoneId: str(r.zone_id) };
  });
  if (!items.length) throw new Invalid();
  return { price: need(num(d.price)), marginUsd: num(d.margin_usd) ?? 0, items, insertAt: need(num(d.insert_at)),
    nearestUp: str(d.nearest_up), nearestDown: str(d.nearest_down), testing: strings(d.testing),
    outside: enumOrNull(LADDER_OUTSIDE, d.outside), positionVsPivot: enumOrNull(PIVOT_POSITIONS, d.position_vs_pivot),
    frame: enumOf(REFERENCE_FRAMES, d.frame) };
};
/** Başlık merdiveni zorunlu (kartın konusu o); tek bir dönem seti bozuksa yalnız o set `null`. */
const parsePivots = (raw: unknown): Pivots | null => block(() => {
  const d = need(obj(raw)); const h = need(obj(d.headline)); const setsRaw = obj(d.sets) ?? {};
  const headline: PivotHeadline = { ...parsePeriodInfo(h), method: enumOf(PIVOT_METHODS, h.method),
    levels: parsePivotLevels(h.levels), ladder: parseLadder(h.ladder) };
  const sets = {} as Pivots['sets'];
  for (const key of ['daily', 'weekly', 'monthly'] as const) {
    sets[key] = block(() => { const s = need(obj(setsRaw[key])); return { ...parsePeriodInfo(s),
      classic: parsePivotLevels(s.classic), fibonacci: parsePivotLevels(s.fibonacci), camarilla: parsePivotLevels(s.camarilla) }; });
  }
  return { status: statusOf(d), pivotMethod: enumOf(PIVOT_METHODS, d.pivot_method), pivotPeriod: enumOf(PIVOT_PERIODS, d.pivot_period),
    minCandles: num(d.min_candles) ?? 0, headline, sets };
});

const parseZone = (raw: unknown): Zone => {
  const d = need(obj(raw));
  return {
    id: need(str(d.id)), mid: need(num(d.mid)), low: need(num(d.low)), high: need(num(d.high)), kind: enumOf(ZONE_KINDS, d.kind),
    strength: need(num(d.strength)), label: enumOf(STRENGTH_LABELS, d.label), name: need(str(d.name)),
    sources: arr(d.sources).map((s): ZoneSource => { const r = need(obj(s)); return { price: need(num(r.price)),
      sourceType: need(str(r.source_type)), label: need(str(r.label)), weight: num(r.weight) ?? 0, date: str(r.date), confirmed: r.confirmed === true }; }),
    sourceTypes: strings(d.source_types), touches: num(d.touches) ?? 0, rejections: num(d.rejections) ?? 0, breaks: num(d.breaks) ?? 0,
    pending: num(d.pending) ?? 0, lastTouch: str(d.last_touch), lastBreak: str(d.last_break), confirmed: d.confirmed === true,
    components: numMap(d.components), distancePct: need(num(d.distance_pct)), distanceUsd: need(num(d.distance_usd)),
    distanceAtr: num(d.distance_atr), distanceSigma: num(d.distance_sigma), testing: d.testing === true,
  };
};
const parseLevels = (raw: unknown): Levels | null => block(() => {
  const d = need(obj(raw)); const side = obj(d.side_status) ?? {};
  const zones = arr(d.zones).map(parseZone);
  if (!zones.length) throw new Invalid();
  return { status: statusOf(d), asOf: str(d.as_of), atr: num(d.atr), sigma: num(d.sigma), marginUsd: num(d.margin_usd),
    minStrength: num(d.min_strength), zones, nearestSupport: str(d.nearest_support), nextSupport: str(d.next_support),
    nearestResistance: str(d.nearest_resistance), nextResistance: str(d.next_resistance), testing: strings(d.testing),
    sideStatus: { support: str(side.support) ?? 'UNKNOWN', resistance: str(side.resistance) ?? 'UNKNOWN' } };
});

const parseMomentumDaily = (raw: unknown): MomentumDaily | null => block(() => {
  const d = need(obj(raw));
  return { status: statusOf(d), date: str(d.date), score: need(num(d.score)), direction: enumOf(DIRECTIONS, d.direction),
    strength: enumOf(STRENGTH_LABELS, d.strength), trend: enumOf(MOMENTUM_TRENDS, d.trend), agreement: need(num(d.agreement)),
    z: num(d.z) ?? 0, delta: num(d.delta) ?? 0, acceleration: num(d.acceleration) ?? 0, note: str(d.note),
    components: numMap(d.components), weights: numMap(d.weights), zScale: num(d.z_scale),
    history: arr(d.history).map(num).filter((v): v is number => v !== null), sigma: num(d.sigma), atr: num(d.atr) };
});

const parseBreakoutSide = (raw: unknown): BreakoutSide => {
  const d = need(obj(raw)); const t = d.target == null ? null : need(obj(d.target));
  const side: BreakoutSide = {
    status: statusOf(d),
    target: t && { zoneId: str(t.zone_id), name: need(str(t.name)), value: need(num(t.value)), zoneStrength: num(t.zone_strength), fallback: t.fallback === true },
    distanceUsd: num(d.distance_usd), distancePct: num(d.distance_pct), distanceAtr: num(d.distance_atr), distanceSigma: num(d.distance_sigma),
    reach: num(d.reach), push: num(d.push), damping: num(d.damping), components: numMap(d.components), strength: num(d.strength),
    label: enumOrNull(STRENGTH_LABELS, d.label), note: str(d.note),
  };
  // Hedefsiz yan meşru (`NO_TARGET_ABOVE`), ama `OK` diyen yan hedef/güç/etiket taşımak zorunda.
  if (side.status === 'OK' && (!side.target || side.strength === null || !side.label)) throw new Invalid();
  return side;
};
const parseBreakout = (raw: unknown): Breakout | null => block(() => {
  const d = need(obj(raw)); const w = obj(d.weights) ?? {};
  return { status: statusOf(d), note: str(d.note), headline: enumOrNull(BREAKOUT_SIDES, d.headline),
    sessionDirection: enumOrNull(DIRECTIONS, d.session_direction), sessionStrength: num(d.session_strength),
    dailyDirection: enumOrNull(DIRECTIONS, d.daily_direction), dailyScore: num(d.daily_score), expectedMove: num(d.expected_move),
    expectedMoveFrame: enumOrNull(EXPECTED_MOVE_FRAMES, d.expected_move_frame), expectedMovePct: num(d.expected_move_pct),
    weights: { session: num(w.session) ?? 0, daily: num(w.daily) ?? 0 }, up: parseBreakoutSide(d.up), down: parseBreakoutSide(d.down) };
});

const parseTrendRange = (raw: unknown): TrendRange => {
  const d = need(obj(raw)); const f = d.fit == null ? null : need(obj(d.fit));
  return {
    id: need(str(d.id)), timeframe: enumOf(TIMEFRAMES, d.timeframe), bars: num(d.bars) ?? 0, candles: d.candles === true,
    status: statusOf(d), lastBucketForming: d.last_bucket_forming === true,
    fit: f && { n: need(num(f.n)), intercept: need(num(f.intercept)), slope: need(num(f.slope)), slopePct: need(num(f.slope_pct)),
      first: need(num(f.first)), last: need(num(f.last)), r2: need(num(f.r2)), changePct: need(num(f.change_pct)),
      direction: enumOf(TREND_DIRECTIONS, f.direction), sigma: need(num(f.sigma)), lastZ: need(num(f.last_z)) },
    realizedPct: num(d.realized_pct), channelState: enumOrNull(CHANNEL_STATES, d.channel_state), fitState: enumOrNull(FIT_STATES, d.fit_state),
    rows: arr(d.rows).map((row): TrendRow => {
      const r = need(obj(row)); const high = need(num(r.h)), low = need(num(r.l));
      return { date: need(str(r.d)), high, low, close: need(num(r.c)), prevClose: num(r.pc), wickHigh: num(r.wh) ?? high,
        wickLow: num(r.wl) ?? low, fit: num(r.fit), b1: pair(r.b1), b2: pair(r.b2), complete: r.complete === true };
    }),
  };
};
const parseTrend = (raw: unknown): Trend | null => block(() => {
  const d = need(obj(raw)); const ranges: Record<string, TrendRange> = {};
  for (const [key, value] of Object.entries(need(obj(d.ranges)))) ranges[key] = parseTrendRange(value);
  if (!Object.keys(ranges).length) throw new Invalid();
  return { status: statusOf(d), ranges };
});

/**
 * `status` ve `reference` yoksa yanıtın tamamı reddedilir; kalan her blok kendi
 * başına düşer. `session` bloğu **değiştirilmeden** `parseMomentum`'a verilir:
 * matematik momentum ucundakiyle aynı, fazladan gelen `status/frame/stale/...`
 * anahtarları o ayrıştırıcı zaten yok sayar ve gün içi veri yokken (`price`
 * gelmez) `null` döner — istenen davranış tam olarak bu. Meta ayrıca okunur.
 */
export const parseTechnical = (raw: unknown): Technical | null => {
  const d = obj(raw); if (!d) return null;
  const statusRaw = obj(d.status); if (!statusRaw) return null;
  const reference = parseReference(d.reference); if (!reference) return null;
  const status = {} as Record<Block, string>;
  for (const key of BLOCKS) status[key] = str(statusRaw[key]) ?? 'MISSING';
  return {
    version: str(d.version) ?? '', generatedAt: str(d.generated_at) ?? '', configHash: str(d.config_hash) ?? '', status, reference,
    daily: parseDaily(d.daily), session: parseMomentum(d.session), sessionMeta: parseSessionMeta(d.session, status.session),
    indicators: parseIndicators(d.indicators), pivots: parsePivots(d.pivots), levels: parseLevels(d.levels),
    momentumDaily: parseMomentumDaily(d.momentum_daily), breakout: parseBreakout(d.breakout), trend: parseTrend(d.trend),
  };
};

export type TechnicalParams = { pivotMethod: PivotMethod; pivotPeriod: PivotPeriod; include?: Block[] };

/**
 * Sorgu elle kurulur: `URLSearchParams` virgülü `%2C` yapar, sunucu ikisini de
 * anlar ama önbellek anahtarı ve loglar okunaklı kalsın. Ağ/şema hatası `null`;
 * iptal (`AbortError`) ise **yükselir** — iptal edilen istek `null` dönseydi
 * çağıran kanca yeni parametrelerin verisini eski isteğin boşuyla ezerdi.
 */
export const fetchTechnical = async (params: TechnicalParams, signal?: AbortSignal): Promise<Technical | null> => {
  const query = [`pivot_method=${params.pivotMethod.toLowerCase()}`, `pivot_period=${params.pivotPeriod.toLowerCase()}`];
  if (params.include?.length) query.push(`include=${params.include.join(',')}`);
  try {
    return parseTechnical(await fetchJson<unknown>(`${marketApi()}/v1/market/xau/technical?${query.join('&')}`, { signal }));
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    return null;
  }
};
