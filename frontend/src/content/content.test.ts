import { describe, expect, it } from 'vitest';
import fixture from '../services/api/__fixtures__/technical.json';
import { money2 } from '../lib/format';
import { INDICATOR_NAME, INDICATOR_STATE, indicatorExtraText } from './indicators';
import { BREAK, DIRECTION as SESSION_DIRECTION, MOMENTUM_DAILY, TREND as SESSION_TREND } from './momentum';
import {
  BREAKOUT_SIDE, COMPLETION, EXPECTED_MOVE_FRAME, FRAME, LEVEL_KIND, LEVEL_ROLE, MARKET_STATE,
  NOTE_TEXT, OUTSIDE, PIVOT_METHOD, PIVOT_PERIOD, POSITION_VS_PIVOT, SOURCE_TYPE, STATUS_TEXT,
  STRENGTH3, sourceLabel,
} from './technical';
import { CHANNEL_STATE, DIRECTION as TREND_DIRECTION, FIT_STATE, RANGE, TIMEFRAME } from './trend';

/* Sunucu yalnız enum anahtarı döner; metin burada üretilir. Sunucuya eklenen
   bir değer sözlüğe yazılmazsa arayüz ham anahtarı basar ve kimse fark etmez.
   Bu test gerçek DTO fixture'ını yol yol gezer: bilinen her enum alanının
   değeri sözlükte olmalı, tanınmayan bir alanda enum'a benzeyen bir değer
   varsa da kural yazılmalı. */

type Leaf = { path: string; value: string };

const leaves = (value: unknown, path = ''): Leaf[] => {
  if (Array.isArray(value)) return value.flatMap(item => leaves(item, `${path}[]`));
  if (value && typeof value === 'object') {
    return Object.entries(value).flatMap(([key, item]) => leaves(item, path ? `${path}.${key}` : key));
  }
  return typeof value === 'string' ? [{ path, value }] : [];
};

const has = (dict: Record<string, unknown>) => (value: string) => value in dict;
const parsed = (value: string) => sourceLabel(value) !== value;

/** Yol deseni → değerin sözlükte olup olmadığı. */
const RULES: [RegExp, (value: string) => boolean][] = [
  [/^status\.\w+$/, has(STATUS_TEXT)],
  [/^(daily|session|indicators|pivots|levels|momentum_daily|breakout|trend|reference)\.status$/, has(STATUS_TEXT)],
  [/^pivots\.(headline|sets\.\w+)\.status$/, has(STATUS_TEXT)],
  [/^trend\.ranges\.\w+\.status$/, has(STATUS_TEXT)],
  [/^levels\.side_status\.\w+$/, has(STATUS_TEXT)],
  [/^breakout\.(up|down)\.status$/, has(STATUS_TEXT)],
  [/^(reference|pivots\.headline\.ladder)\.frame$/, has(FRAME)],
  [/^reference\.note$/, has(NOTE_TEXT)],
  [/^breakout\.(note|(up|down)\.note)$/, has(NOTE_TEXT)],
  [/^breakout\.(up|down)\.label$/, has(STRENGTH3)],
  [/^breakout\.(up|down)\.target\.name$/, parsed],
  [/^breakout\.expected_move_frame$/, has(EXPECTED_MOVE_FRAME)],
  [/^breakout\.headline$/, has(BREAKOUT_SIDE)],
  [/^breakout\.session_direction$/, has(SESSION_DIRECTION)],
  [/^breakout\.daily_direction$/, has(MOMENTUM_DAILY.direction)],
  [/^indicators\.rows\[\]\.key$/, has(INDICATOR_NAME)],
  [/^indicators\.rows\[\]\.state$/, has(INDICATOR_STATE)],
  [/^levels\.zones\[\]\.kind$/, has(LEVEL_KIND)],
  [/^levels\.zones\[\]\.label$/, has(STRENGTH3)],
  [/^levels\.zones\[\]\.(name|sources\[\]\.label)$/, parsed],
  [/^levels\.zones\[\]\.(source_types\[\]|sources\[\]\.source_type)$/, has(SOURCE_TYPE)],
  [/^momentum_daily\.direction$/, has(MOMENTUM_DAILY.direction)],
  [/^momentum_daily\.strength$/, has(MOMENTUM_DAILY.strength)],
  [/^momentum_daily\.trend$/, has(MOMENTUM_DAILY.trend)],
  [/^momentum_daily\.note$/, has(MOMENTUM_DAILY.note)],
  [/^pivots\.(headline|sets\.\w+)\.completion$/, has(COMPLETION)],
  [/^pivots\.headline\.ladder\.items\[\]\.role$/, has(LEVEL_ROLE)],
  [/^pivots\.headline\.ladder\.position_vs_pivot$/, has(POSITION_VS_PIVOT)],
  [/^pivots\.headline\.ladder\.outside$/, has(OUTSIDE)],
  [/^pivots\.(pivot_method|headline\.method)$/, has(PIVOT_METHOD)],
  [/^pivots\.(pivot_period|headline\.period|sets\.\w+\.period)$/, has(PIVOT_PERIOD)],
  [/^session\.market_state$/, has(MARKET_STATE)],
  [/^session\.direction$/, has(SESSION_DIRECTION)],
  [/^session\.trend$/, has(SESSION_TREND)],
  [/^trend\.ranges\.\w+\.channel_state$/, has(CHANNEL_STATE)],
  [/^trend\.ranges\.\w+\.fit_state$/, has(FIT_STATE)],
  [/^trend\.ranges\.\w+\.fit\.direction$/, has(TREND_DIRECTION)],
  [/^trend\.ranges\.\w+\.timeframe$/, has(TIMEFRAME)],
  [/^trend\.ranges\.\w+\.id$/, has(RANGE)],
];

/** Enum olmayan metin alanları: kimlik, tarih, ad, kaynak bilgisi. */
const NOT_ENUMS: RegExp[] = [
  /^(version|config_hash|generated_at)$/,
  /^meta\./,
  /^daily\.(body_definition|candles|change|quality)/,
  /^reference\.(instrument|as_of|daily_date|source\.)/,
  /^session\.(frame|instrument|session_date|error|as_of)$/,
  // Eski gün içi bloğun seviye alanları: arayüz okumuyor (seviyeler pivot
  // merdiveninden gelir), sözlüğü de eski (`MEDIUM`).
  /^session\.(breakout|ladder|support|resistance|touching)\b/,
  /^indicators\.date$/,
  /^momentum_daily\.date$/,
  /^pivots\.(headline|sets\.\w+)\.(period_id|start|end|missing_bar_for)$/,
  /^pivots\.headline\.levels\[\]\[\]$/,
  /^pivots\.sets\.\w+\.(classic|fibonacci|camarilla)\[\]\[\]$/,
  /^pivots\.headline\.ladder\.(items\[\]\.(name|zone_id)|nearest_up|nearest_down|testing\[\])$/,
  /^levels\.(as_of|nearest_\w+|next_\w+|testing\[\])$/,
  /^levels\.zones\[\]\.(id|last_touch|last_break|sources\[\]\.date)$/,
  /^levels\.weakest_ignored/,
  /^breakout\.(up|down)\.target\.zone_id$/,
  /^trend\.ranges\.\w+\.rows\[\]\.d$/,
];

const ENUM_LIKE = /^[A-Za-z][A-Za-z0-9_]*$/;

describe('teknik DTO sözlüğü', () => {
  const all = leaves(fixture);

  it('fixture bir şey taşıyor', () => {
    expect(all.length).toBeGreaterThan(100);
  });

  it('fixture içindeki her enum değeri sözlükte', () => {
    const unmapped: string[] = [];
    const unknown: string[] = [];
    for (const { path, value } of all) {
      const rule = RULES.find(([pattern]) => pattern.test(path));
      if (rule) {
        if (!rule[1](value)) unmapped.push(`${path} = ${value}`);
        continue;
      }
      if (NOT_ENUMS.some(pattern => pattern.test(path))) continue;
      if (ENUM_LIKE.test(value)) unknown.push(`${path} = ${value}`);
    }
    expect(unmapped, 'sözlükte karşılığı olmayan enum değerleri').toEqual([]);
    expect(unknown, 'kuralı yazılmamış enum benzeri alanlar').toEqual([]);
  });

  it('kuralların çoğu fixture ile karşılaştı (bayat desen yok)', () => {
    // `outside` ve `headline` fixture'da null; kalan her desen en az bir yaprağa değmeli.
    const optional = [/outside/, /headline\$$/];
    const idle = RULES
      .map(([pattern]) => pattern)
      .filter(pattern => !optional.some(o => o.test(pattern.source)))
      .filter(pattern => !all.some(({ path }) => pattern.test(path)));
    expect(idle.map(p => p.source)).toEqual([]);
  });
});

describe('sözlük içerikleri', () => {
  it('OK dışındaki her durumun boş durum cümlesi var', () => {
    for (const [key, text] of Object.entries(STATUS_TEXT)) {
      if (key === 'OK') expect(text).toBeNull();
      else expect(text, key).toMatch(/\S/);
    }
  });

  it('sourceLabel üç kalıbı ve dönem öneklerini çözer', () => {
    expect(sourceLabel('SWING_HIGH')).toBe('salınım zirvesi');
    expect(sourceLabel('SWING_LOW')).toBe('salınım dibi');
    expect(sourceLabel('HIGH_20')).toBe('20 günlük zirve');
    expect(sourceLabel('LOW_250')).toBe('250 günlük dip');
    expect(sourceLabel('ROUND')).toBe('yuvarlak seviye');
    expect(sourceLabel('W_R1')).toBe('Haftalık R1');
    expect(sourceLabel('M_P')).toBe('Aylık P');
    expect(sourceLabel('D_P')).toBe('Günlük P');
    expect(sourceLabel('R1')).toBe('R1');
  });

  it('BREAK yalnız sunucu etiketlerini taşır; eski MEDIUM alias yok', () => {
    expect(Object.keys(BREAK).sort()).toEqual(['MODERATE', 'STRONG', 'WEAK']);
    expect(BREAK.MODERATE.label).toBe('ORTA');
  });

  it('indicatorExtraText ikinci satırı tr-TR biçimiyle kurar', () => {
    expect(indicatorExtraText('stochastic', { d: 40.313353 })).toBe('%D 40,3');
    expect(indicatorExtraText('macd', { signal: 80.388249, histogram: -20.624209 }))
      .toBe('Sinyal 80,4 · Histogram −20,6');
    expect(indicatorExtraText('adx', { plus_di: 30.980283, minus_di: 29.061023 }))
      .toBe('+DI 31,0 · −DI 29,1');
    expect(indicatorExtraText('atr', { median: 82.976317 })).toBe(`Medyan ${money2(82.976317)}`);
    expect(indicatorExtraText('rsi', {})).toBeNull();
    expect(indicatorExtraText('macd', { signal: null, histogram: undefined })).toBeNull();
  });
});
