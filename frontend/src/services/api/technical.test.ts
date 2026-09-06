import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/technical.json';
import { BLOCKS, fetchTechnical, parseTechnical, type Technical } from './technical';

/* Fikstür gerçek boru hattından üretildi; her test kendi kopyasını bozar. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const load = (): any => structuredClone(fixture);
const PARSED: Record<typeof BLOCKS[number], keyof Technical> = {
  daily: 'daily', session: 'session', indicators: 'indicators', pivots: 'pivots', levels: 'levels',
  momentum_daily: 'momentumDaily', breakout: 'breakout', trend: 'trend',
};
const others = (out: Technical, except: keyof Technical) =>
  Object.values(PARSED).filter(key => key !== except).map(key => [key, out[key] !== null]);
const allOn = (out: Technical, except: keyof Technical) =>
  expect(others(out, except)).toEqual(others(out, except).map(([key]) => [key, true]));

describe('parseTechnical — tam fikstür', () => {
  const out = parseTechnical(load())!;

  it('tüm bloklar ve üst bilgi okunur', () => {
    expect(out).not.toBeNull();
    for (const key of Object.values(PARSED)) expect(out[key], key).not.toBeNull();
    expect(out.version).toBe('technical-v1');
    expect(out.generatedAt).toBe('2026-09-06T10:02:05Z');
    expect(out.configHash).toBe('8cc57c8db10f');
    expect(Object.values(out.status)).toEqual(BLOCKS.map(() => 'OK'));
  });

  it('referans fiyat gün içi kapanıştır', () => {
    expect(out.reference.value).toBe(4476.6);
    expect(out.reference.frame).toBe('intraday_close');
    expect(out.reference.instrument).toBe('GC=F');
    expect(out.reference.dailyClose).toBe(4476.6);
    expect(out.reference.source.dailyFallback).toBe(false);
  });

  it('günlük hareket ve mumlar (önceki kapanış gövde referansı)', () => {
    expect(out.daily!.change!.usd).toBe(-15.1);
    expect(out.daily!.change!.previousClose).toBe(4491.7);
    expect(out.daily!.candles).toHaveLength(1257);
    expect(out.daily!.candles.at(-1)).toEqual({ date: '2026-09-04', high: 4537.8, low: 4412.0, close: 4476.6, prevClose: 4491.7 });
    expect(out.daily!.candles[0].prevClose).toBeNull();
    expect(out.daily!.quality.lastIsForming).toBe(false);
    expect(out.daily!.bodyDefinition).toBe('prev_close_to_close');
  });

  it('seans bloğu parseMomentum ile okunur, meta ayrı taşınır', () => {
    expect(out.session!.strength).toBe(22);
    expect(out.session!.direction).toBe('NEUTRAL');
    expect(out.session!.trend).toBe('STABLE');
    expect(out.session!.session.expectedMove).toBe(53.25);
    expect(out.sessionMeta).toEqual({ status: 'OK', frame: 'intraday_5m', instrument: 'GC=F', stale: false,
      marketState: 'CLOSED', sessionDate: '2026-09-04', error: null });
  });

  it('göstergeler: 8 satır, 6 hareketli ortalama', () => {
    expect(out.indicators!.rows).toHaveLength(8);
    expect(out.indicators!.movingAverages).toHaveLength(6);
    expect(out.indicators!.rows.find(r => r.key === 'macd')).toEqual({ key: 'macd', value: 59.76404, state: 'BELOW_SIGNAL',
      extra: { signal: 80.388249, histogram: -20.624209 } });
    expect(out.indicators!.rows.find(r => r.key === 'atr')!.state).toBe('NORMAL_VOLATILITY');
    expect(out.indicators!.movingAverages[0]).toEqual({ period: 5, sma: 4422.74, ema: 4458.289052, priceAboveSma: true });
    expect(out.indicators!.atr).toBeCloseTo(86.656758);
  });

  it('pivot başlığı ve merdiven (eski alan adları korunur)', () => {
    const { headline } = out.pivots!;
    expect(out.pivots!.pivotMethod).toBe('CLASSIC');
    expect(out.pivots!.pivotPeriod).toBe('WEEKLY');
    expect(headline.periodId).toBe('2026-08-31');
    expect(headline.levels).toHaveLength(7);
    expect(headline.ladder.items).toHaveLength(7);
    expect(headline.ladder.nearestUp).toBe('R1');
    expect(headline.ladder.nearestDown).toBe('P');
    expect(headline.ladder.insertAt).toBe(3);
    expect(headline.ladder.positionVsPivot).toBe('ABOVE');
    expect(headline.ladder.frame).toBe('intraday_close');
    expect(headline.ladder.outside).toBeNull();
    expect(headline.ladder.items[2]).toMatchObject({ name: 'R1', above: true, role: 'NEAREST_UP', zoneId: 'z-4587',
      distanceUsd: 102.266667, band: [4567.4195, 4590.313833] });
    expect(headline.ladder.items[3]).toMatchObject({ name: 'P', above: false, role: 'NEAREST_DOWN', zoneId: 'z-4441' });
  });

  it('pivot setleri: üç dönem × üç yöntem', () => {
    const { sets } = out.pivots!;
    for (const key of ['daily', 'weekly', 'monthly'] as const) {
      expect(sets[key]!.classic).toHaveLength(7);
      expect(sets[key]!.fibonacci).toHaveLength(7);
      expect(sets[key]!.camarilla).toHaveLength(9);
      expect(sets[key]!.completion).toBe('LAST_BAR_PRESENT');
    }
    expect(sets.daily!.camarilla[0]).toEqual({ name: 'R4', value: 4545.79 });
    expect(sets.monthly!.periodId).toBe('2026-08');
  });

  it('yapısal bölgeler ve en yakınlar', () => {
    const levels = out.levels!;
    expect(levels.zones).toHaveLength(24);
    expect(levels.nearestSupport).toBe('z-4354');
    expect(levels.nextSupport).toBe('z-4265');
    expect(levels.nearestResistance).toBe('z-4533');
    expect(levels.testing).toContain('z-4441');
    expect(levels.sideStatus).toEqual({ support: 'OK', resistance: 'OK' });
    expect(levels.zones[0]).toMatchObject({ id: 'z-4587', kind: 'RESISTANCE', label: 'STRONG', strength: 74, touches: 7 });
    expect(levels.zones[0].sources).toHaveLength(3);
    expect(levels.zones[0].sources[1]).toEqual({ price: 4591.8, sourceType: 'swing', label: 'SWING_HIGH', weight: 1, date: '2026-05-29', confirmed: true });
    expect(levels.zones[0].components.touch).toBeCloseTo(0.692182);
  });

  it('günlük momentum', () => {
    expect(out.momentumDaily).toMatchObject({ score: 59, direction: 'NEUTRAL', strength: 'WEAK', trend: 'STRENGTHENING', note: 'CONFLICTING' });
    expect(out.momentumDaily!.history).toHaveLength(30);
    expect(out.momentumDaily!.weights.velocity).toBe(0.25);
  });

  it('iki yönlü kırılım', () => {
    const b = out.breakout!;
    expect(b.headline).toBeNull();
    expect(b.up).toMatchObject({ status: 'OK', strength: 43, label: 'MODERATE' });
    expect(b.up.target).toEqual({ zoneId: 'z-4533', name: 'SWING_LOW', value: 4532.555556, zoneStrength: 31, fallback: false });
    expect(b.down).toMatchObject({ strength: 19, label: 'WEAK' });
    expect(b.expectedMoveFrame).toBe('session_remaining');
    expect(b.weights).toEqual({ session: 0.6, daily: 0.4 });
  });

  it('trend: beş aralık, günlük 90 satır ve bantlar', () => {
    const { ranges } = out.trend!;
    expect(Object.keys(ranges)).toEqual(['gunluk', 'haftalik', 'aylik', 'ceyreklik', 'yarim']);
    const gunluk = ranges.gunluk;
    expect(gunluk.rows).toHaveLength(90);
    expect(gunluk).toMatchObject({ timeframe: 'DAILY', candles: true, channelState: 'ABOVE_1SIGMA', fitState: 'WEAK' });
    expect(gunluk.fit!.direction).toBe('DOWN');
    expect(gunluk.rows[1]).toMatchObject({ date: '2026-04-30', prevClose: 4545.2, wickLow: 4545.2,
      b1: [4220.317898, 4666.653859], b2: [4013.423174, 4907.223074], complete: true });
    expect(ranges.haftalik.lastBucketForming).toBe(true);
    expect(ranges.haftalik.rows.at(-1)!.complete).toBe(false);
    expect(ranges.ceyreklik.rows[0].prevClose).toBeNull();
  });
});

describe('parseTechnical — zorunlu üst alanlar', () => {
  it('status yoksa yanıtın tamamı reddedilir', () => {
    const raw = load(); delete raw.status;
    expect(parseTechnical(raw)).toBeNull();
    expect(parseTechnical({ ...load(), status: 'OK' })).toBeNull();
  });

  it('reference yoksa ya da bozuksa yanıtın tamamı reddedilir', () => {
    const raw = load(); delete raw.reference;
    expect(parseTechnical(raw)).toBeNull();
    expect(parseTechnical({ ...load(), reference: { ...load().reference, value: 'x' } })).toBeNull();
    expect(parseTechnical({ ...load(), reference: { ...load().reference, frame: 'live_quote' } })).toBeNull();
  });

  it('referans değeri null olabilir (günlük kapanış çerçevesi)', () => {
    const out = parseTechnical({ ...load(), reference: { ...load().reference, value: null, frame: 'daily_close' } })!;
    expect(out.reference.value).toBeNull();
    expect(out.reference.frame).toBe('daily_close');
  });

  it('kendi başına yanıt olmayan girdiler null', () => {
    expect(parseTechnical(null)).toBeNull();
    expect(parseTechnical('yanıt değil')).toBeNull();
    expect(parseTechnical([])).toBeNull();
  });
});

describe('parseTechnical — bloklar bağımsız düşer', () => {
  it.each([
    ['daily', (r: any) => { r.daily.candles = 'x'; }],
    ['daily', (r: any) => { r.daily.candles[3][1] = 'yüksek'; }],
    ['session', (r: any) => { delete r.session.price; }],
    ['indicators', (r: any) => { r.indicators.rows[0].state = 'BANANA'; }],
    ['indicators', (r: any) => { r.indicators.rows = []; }],
    ['pivots', (r: any) => { r.pivots.headline.ladder.items = null; }],
    ['pivots', (r: any) => { r.pivots.headline = null; }],
    ['pivots', (r: any) => { r.pivots.headline.ladder.items[0].role = 'MIDDLE'; }],
    ['levels', (r: any) => { r.levels.zones[0].kind = 'SIDEWAYS'; }],
    ['levels', (r: any) => { r.levels.zones = []; }],
    ['momentum_daily', (r: any) => { r.momentum_daily.score = 'x'; }],
    ['momentum_daily', (r: any) => { r.momentum_daily.direction = 'FLAT'; }],
    ['breakout', (r: any) => { r.breakout.up.label = 'HUGE'; }],
    ['breakout', (r: any) => { r.breakout.headline = 'sideways'; }],
    ['breakout', (r: any) => { r.breakout.up.target = null; }],
    ['trend', (r: any) => { r.trend.ranges.gunluk.channel_state = 'MOON'; }],
    ['trend', (r: any) => { r.trend.ranges.haftalik.fit_state = 'PERFECT'; }],
    ['trend', (r: any) => { r.trend.ranges.aylik.timeframe = 'BIWEEKLY'; }],
  ] as const)('%s bloğu bozulunca yalnız o blok null', (blockKey, mutate) => {
    const raw = load(); mutate(raw);
    const out = parseTechnical(raw)!;
    expect(out).not.toBeNull();
    expect(out[PARSED[blockKey]]).toBeNull();
    allOn(out, PARSED[blockKey]);
  });

  it.each(BLOCKS)('%s bloğu hiç gelmezse yalnız o blok null', blockKey => {
    const raw = load(); delete raw[blockKey];
    const out = parseTechnical(raw)!;
    expect(out[PARSED[blockKey]]).toBeNull();
    allOn(out, PARSED[blockKey]);
    expect(out.status[blockKey]).toBe('OK');
  });

  it('include alt kümesi: yalnız istenen bloklar dolu, diğerleri null, fırlatmaz', () => {
    const full = load();
    const raw = { version: full.version, generated_at: full.generated_at, config_hash: full.config_hash,
      meta: { blocks: ['pivots', 'breakout'] }, status: full.status, reference: full.reference, pivots: full.pivots, breakout: full.breakout };
    const out = parseTechnical(raw)!;
    expect(out.pivots).not.toBeNull();
    expect(out.breakout).not.toBeNull();
    for (const key of ['daily', 'session', 'indicators', 'levels', 'momentumDaily', 'trend'] as const) expect(out[key]).toBeNull();
    expect(out.sessionMeta.status).toBe('OK');
  });

  it('eksik status anahtarı MISSING olarak işaretlenir, yanıt yine okunur', () => {
    const raw = load(); delete raw.status.trend;
    expect(parseTechnical(raw)!.status.trend).toBe('MISSING');
  });

  /* Gün içi veri yokken sunucu yalnız meta gönderir; kart "neden yok"u yazabilmeli. */
  it('INTRADAY_UNAVAILABLE seans: momentum null, meta korunur', () => {
    const raw = load();
    raw.status.session = 'INTRADAY_UNAVAILABLE';
    raw.session = { status: 'INTRADAY_UNAVAILABLE', frame: 'intraday_5m', instrument: 'GC=F', stale: false,
      market_state: null, session_date: null, error: null };
    const out = parseTechnical(raw)!;
    expect(out.session).toBeNull();
    expect(out.sessionMeta).toEqual({ status: 'INTRADAY_UNAVAILABLE', frame: 'intraday_5m', instrument: 'GC=F', stale: false,
      marketState: null, sessionDate: null, error: null });
    allOn(out, 'session');
  });

  it('INTRADAY_STALE seans: momentum okunur, meta bayat der', () => {
    const raw = load();
    raw.session.status = 'INTRADAY_STALE'; raw.session.stale = true; raw.session.market_state = 'HALTED';
    const out = parseTechnical(raw)!;
    expect(out.session!.strength).toBe(22);
    expect(out.sessionMeta.stale).toBe(true);
    expect(out.sessionMeta.status).toBe('INTRADAY_STALE');
    expect(out.sessionMeta.marketState).toBeNull();
  });

  it('hedefsiz kırılım yanı meşrudur', () => {
    const raw = load();
    raw.breakout.up = { status: 'NO_TARGET_ABOVE', target: null, distance_usd: null, distance_pct: null, distance_atr: null,
      distance_sigma: null, reach: null, push: null, damping: null, components: {}, strength: null, label: null, note: null };
    const out = parseTechnical(raw)!;
    expect(out.breakout!.up).toMatchObject({ status: 'NO_TARGET_ABOVE', target: null, strength: null, label: null });
    expect(out.breakout!.down.strength).toBe(19);
  });

  it('tek bir pivot seti bozuksa yalnız o set null, blok ayakta', () => {
    const raw = load(); raw.pivots.sets.monthly.camarilla = 'x';
    const out = parseTechnical(raw)!;
    expect(out.pivots!.sets.monthly).toBeNull();
    expect(out.pivots!.sets.weekly).not.toBeNull();
    expect(out.pivots!.headline.ladder.items).toHaveLength(7);
  });

  it('gösterge durumu null olabilir (veri yetersiz), bilinmeyen olamaz', () => {
    const raw = load(); raw.indicators.rows[0].state = null; raw.indicators.rows[0].value = null;
    expect(parseTechnical(raw)!.indicators!.rows[0]).toEqual({ key: 'rsi', value: null, state: null, extra: {} });
  });
});

describe('fetchTechnical', () => {
  afterEach(() => vi.unstubAllGlobals());
  const stub = (response: Partial<Response> & { json?: () => Promise<unknown> }) => {
    const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => load(), ...response }));
    vi.stubGlobal('fetch', fetchMock);
    return fetchMock;
  };

  it('sorguyu küçük harfle ve virgüllü include ile kurar', async () => {
    const fetchMock = stub({});
    const out = await fetchTechnical({ pivotMethod: 'CAMARILLA', pivotPeriod: 'DAILY', include: ['pivots', 'breakout'] });
    expect(out!.pivots!.headline.ladder.items).toHaveLength(7);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/market-service/v1/market/xau/technical?pivot_method=camarilla&pivot_period=daily&include=pivots,breakout');
    expect(init.signal).toBeUndefined();
  });

  it('include verilmezse parametre hiç yazılmaz, sinyal iletilir', async () => {
    const fetchMock = stub({});
    const controller = new AbortController();
    await fetchTechnical({ pivotMethod: 'CLASSIC', pivotPeriod: 'WEEKLY' }, controller.signal);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/market-service/v1/market/xau/technical?pivot_method=classic&pivot_period=weekly');
    expect(init.signal).toBe(controller.signal);
  });

  it('OK olmayan yanıt null', async () => {
    stub({ ok: false, status: 503 });
    await expect(fetchTechnical({ pivotMethod: 'CLASSIC', pivotPeriod: 'WEEKLY' })).resolves.toBeNull();
  });

  it('şeması bozuk gövde null', async () => {
    stub({ json: async () => ({ version: 'technical-v1' }) });
    await expect(fetchTechnical({ pivotMethod: 'CLASSIC', pivotPeriod: 'WEEKLY' })).resolves.toBeNull();
  });

  /* İptal `null` sayılsaydı kanca yeni isteğin verisini eski isteğin boşuyla ezerdi. */
  it('iptal null değil, hata olarak yükselir', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new DOMException('aborted', 'AbortError'); }));
    await expect(fetchTechnical({ pivotMethod: 'CLASSIC', pivotPeriod: 'WEEKLY' })).rejects.toThrow('aborted');
  });
});
