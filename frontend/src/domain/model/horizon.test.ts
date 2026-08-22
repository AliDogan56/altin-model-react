import { describe, expect, it } from 'vitest';
import { resolveHorizon } from './horizon';

describe('resolveHorizon', () => {
  it('tam eşleşmeyi seçer', () => {
    expect(resolveHorizon([7, 14, 30], 14)).toEqual({ index: 1, horizon: 14, exact: true });
  });

  /* Önceden `Math.max(0, indexOf(x))` kullanılıyordu: listede olmayan ufuk
     sessizce ilk ufka (7 gün) düşüyor ve kart yanlış vadeyi anlatıyordu. */
  it('listede olmayan ufukta en yakınına düşer ve bunu bildirir', () => {
    expect(resolveHorizon([7, 14, 30], 90)).toEqual({ index: 2, horizon: 30, exact: false });
    expect(resolveHorizon([7, 14, 30], 1)).toEqual({ index: 0, horizon: 7, exact: false });
    expect(resolveHorizon([7, 14, 30], 20)).toEqual({ index: 1, horizon: 14, exact: false });
  });

  it('eşit uzaklıkta küçük ufku seçer', () => {
    expect(resolveHorizon([10, 20], 15)).toEqual({ index: 0, horizon: 10, exact: false });
  });

  it('boş listede güvenli değer döner', () => {
    expect(resolveHorizon([], 30)).toEqual({ index: 0, horizon: 30, exact: false });
  });
});
