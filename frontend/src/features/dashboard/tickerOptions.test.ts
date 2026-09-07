import { describe, expect, it } from 'vitest';
import { DEFAULT_SLOTS, SLOT_COUNT, TICKER_OPTIONS, applySlot, normalizeSlots, optionOf, tickerValue } from './tickerOptions';

const quote = (satis: number) => ({ alis: satis - 10, satis, dir: '', low: 0, high: 0, prev: 0, time: '' });

describe('tickerOptions — başlık kartı yuvaları', () => {
  it('varsayılan üç yuva kartın eski sabit hâlidir ve hepsi tanınır', () => {
    expect(DEFAULT_SLOTS).toEqual(['ALTIN', 'dollar_return_5d', 'real_yield_change_5d']);
    expect(DEFAULT_SLOTS.every(id => optionOf(id))).toBe(true);
    expect(new Set(TICKER_OPTIONS.map(o => o.id)).size).toBe(TICKER_OPTIONS.length);
  });

  it('bozuk, eksik ve tekrarlı saklanan seçim varsayılanla tamamlanır', () => {
    expect(normalizeSlots(null)).toEqual([...DEFAULT_SLOTS]);
    expect(normalizeSlots('ALTIN')).toEqual([...DEFAULT_SLOTS]);
    expect(normalizeSlots(['CEYREK_YENI', 'yok', 'CEYREK_YENI'])).toEqual(['CEYREK_YENI', 'ALTIN', 'dollar_return_5d']);
    expect(normalizeSlots(['vix_level', 'ALTIN', 'oil_return_5d', 'core_cpi_yoy'])).toEqual(['vix_level', 'ALTIN', 'oil_return_5d']);
    expect(normalizeSlots([1, {}, undefined])).toHaveLength(SLOT_COUNT);
  });

  it('bir yuvaya seçim atar; başka yuvada seçiliyse ikisi yer değiştirir', () => {
    const base = ['ALTIN', 'dollar_return_5d', 'real_yield_change_5d'];
    expect(applySlot(base, 1, 'vix_level')).toEqual(['ALTIN', 'vix_level', 'real_yield_change_5d']);
    expect(applySlot(base, 0, 'real_yield_change_5d')).toEqual(['real_yield_change_5d', 'dollar_return_5d', 'ALTIN']);
    expect(applySlot(base, 0, 'ALTIN')).toEqual(base);
    expect(applySlot(base, 0, 'bilinmeyen')).toEqual(base);
    expect(applySlot(base, 5, 'vix_level')).toEqual(base);
    expect(applySlot(base, 1, 'vix_level')).not.toBe(base);
  });

  it('değerler türüne göre biçimlenir, veri yoksa null', () => {
    const data = { ziynet: { ALTIN: quote(6847), CEYREK_YENI: quote(11200) },
      live: { dollar_return_5d: 0.0123, real_yield_change_5d: -0.03, vix_level: 17.46, oil_return_5d: -0.021, yield_curve_10y_2y: 0.52, core_cpi_yoy: 2.15 } };
    expect(tickerValue('ALTIN', data)).toBe('₺6.847');
    expect(tickerValue('CEYREK_YENI', data)).toBe('₺11.200');
    expect(tickerValue('YARIM_YENI', data)).toBeNull();
    expect(tickerValue('dollar_return_5d', data)).toBe('%1,2');
    expect(tickerValue('real_yield_change_5d', data)).toBe('-0.03 puan');
    expect(tickerValue('yield_curve_10y_2y', data)).toBe('+0.52 puan');
    expect(tickerValue('vix_level', data)).toBe('17.5');
    expect(tickerValue('oil_return_5d', data)).toBe('-%2,1');
    expect(tickerValue('core_cpi_yoy', data)).toBe('%2,2');
    expect(tickerValue('vix_level', { ziynet: {}, live: {} })).toBeNull();
    expect(tickerValue('yok', data)).toBeNull();
  });
});
