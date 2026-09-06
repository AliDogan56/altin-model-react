import { describe, expect, it } from 'vitest';
import fixture from '../../services/api/__fixtures__/technical.json';
import { parseTechnical, type Technical } from '../../services/api/technical';
import { CLOSED_STALE_MS, SESSION_STALE_MS, STALE_AFTER_MS, isStale, marketSeries, paramsKey, sessionStaleAfterMs } from './useTechnical';

/* Yalnız saf parçalar: kanca DOM ister, vitest ortamı node. */
const technical = (): Technical => parseTechnical(structuredClone(fixture))!;

describe('marketSeries — teknik paketten panel serileri', () => {
  it('veri yokken boş seri ve canlı olmayan boş fiyat', () => {
    expect(marketSeries(null)).toEqual({ history: [], candles: [], lastClose: null, spot: { price: null, time: null, live: false } });
  });

  it('günlük mumlar eski Candle şekline (+pc) ve [tarih, kapanış] çiftlerine çevrilir', () => {
    const out = marketSeries(technical());
    expect(out.history).toHaveLength(1257);
    expect(out.candles).toHaveLength(1257);
    expect(out.history.at(-1)).toEqual(['2026-09-04', 4476.6]);
    expect(out.candles.at(-1)).toEqual({ date: '2026-09-04', h: 4537.8, l: 4412.0, c: 4476.6, pc: 4491.7 });
    expect(out.candles[0].pc).toBeNull();
  });

  it('kapanış ve referans sunucudan gelir; Harem/paket yedeği karışmaz', () => {
    const out = marketSeries(technical());
    expect(out.lastClose).toBe(4476.6);
    expect(out.spot).toEqual({ price: 4476.6, time: new Date('2026-09-04T20:59:58Z'), live: true });
  });

  it('referans değeri yoksa başka çerçeveden doldurulmaz: fiyat null, canlı değil', () => {
    const noValue = technical();
    noValue.reference = { ...noValue.reference, value: null, asOf: null };
    const a = marketSeries(noValue);
    expect(a.spot.price).toBeNull();
    expect(a.spot.live).toBe(false);
    expect(a.spot.time).toEqual(new Date('2026-09-04T00:00:00Z'));

    const noClose = technical();
    noClose.reference = { ...noClose.reference, value: null, dailyClose: null };
    expect(marketSeries(noClose).lastClose).toBeNull();          // son mumun kapanışı **kullanılmaz**
    expect(marketSeries(noClose).spot.live).toBe(false);
  });

  it('günlük blok düşmüşse seriler boş kalır ama referans hâlâ okunur', () => {
    const out = marketSeries({ ...technical(), daily: null });
    expect(out.history).toEqual([]);
    expect(out.candles).toEqual([]);
    expect(out.lastClose).toBe(4476.6);
    expect(out.spot.price).toBe(4476.6);
  });

  it('hiçbir fiyat yoksa canlı sayılmaz', () => {
    const bare = technical();
    bare.daily = null;
    bare.reference = { ...bare.reference, value: null, dailyClose: null };
    expect(marketSeries(bare).spot).toMatchObject({ price: null, live: false });
  });
});

describe('sessionStaleAfterMs — seans verisinin gecikme eşiği', () => {
  const meta = technical().sessionMeta;
  it('piyasa kapalıyken üç gün, açıkken 15 dakika', () => {
    expect(sessionStaleAfterMs({ ...meta, marketState: 'CLOSED', stale: false })).toBe(CLOSED_STALE_MS);
    expect(sessionStaleAfterMs({ ...meta, marketState: 'OPEN', stale: false })).toBe(SESSION_STALE_MS);
    expect(sessionStaleAfterMs(null)).toBe(SESSION_STALE_MS);
  });
  it('sunucu stale diyorsa eşik sıfır: kapalı piyasa bile gecikmeli sayılır', () => {
    expect(sessionStaleAfterMs({ ...meta, marketState: 'CLOSED', stale: true })).toBe(0);
  });
});

describe('yenileme ritmi yardımcıları', () => {
  it('isStale eşiği dahil sayar', () => {
    expect(isStale(0, STALE_AFTER_MS)).toBe(true);
    expect(isStale(0, STALE_AFTER_MS - 1)).toBe(false);
    expect(isStale(1000, 1000 + 60_000, 60_000)).toBe(true);
  });

  it('paramsKey aynı ayarlar için aynı, farklı ayarlar için farklı anahtar verir', () => {
    expect(paramsKey({ pivotMethod: 'CLASSIC', pivotPeriod: 'WEEKLY' })).toBe(paramsKey({ pivotMethod: 'CLASSIC', pivotPeriod: 'WEEKLY' }));
    expect(paramsKey({ pivotMethod: 'CLASSIC', pivotPeriod: 'WEEKLY' })).not.toBe(paramsKey({ pivotMethod: 'FIBONACCI', pivotPeriod: 'WEEKLY' }));
    expect(paramsKey({ pivotMethod: 'CLASSIC', pivotPeriod: 'WEEKLY' })).not.toBe(paramsKey({ pivotMethod: 'CLASSIC', pivotPeriod: 'MONTHLY' }));
  });
});
