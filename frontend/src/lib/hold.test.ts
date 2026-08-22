import { describe, expect, it } from 'vitest';
import { MIN_SPINNER_MS, nextHold, type HoldState } from './hold';

const idle: HoldState = { held: false, startedAt: 0 };

describe('nextHold', () => {
  it('koşul doğduğunda tutmaya başlar ve zamanı işaretler', () => {
    const step = nextHold(idle, true, 1000);
    expect(step.state).toEqual({ held: true, startedAt: 1000 });
    expect(step.timeoutIn).toBeNull();
  });

  it('koşul sürerken sayacı sıfırlamaz', () => {
    // Aksi hâlde her veri güncellemesi asgari süreyi baştan başlatır ve
    // gösterge hiç kaybolmaz.
    const held = nextHold(idle, true, 1000).state;
    const again = nextHold(held, true, 1600).state;
    expect(again.startedAt).toBe(1000);
  });

  it('süre dolmadan koşul biterse kalan süreyi bildirir', () => {
    const held = nextHold(idle, true, 1000).state;
    const step = nextHold(held, false, 1000 + 400);
    expect(step.state.held).toBe(true);          // hâlâ ekranda
    expect(step.timeoutIn).toBe(MIN_SPINNER_MS - 400);
  });

  it('süre dolduktan sonra koşul biterse hemen kaldırır', () => {
    const held = nextHold(idle, true, 1000).state;
    const step = nextHold(held, false, 1000 + MIN_SPINNER_MS);
    expect(step.state.held).toBe(false);
    expect(step.timeoutIn).toBeNull();
  });

  it('anlık gelen veride bile göstergeyi bir dolum boyunca tutar', () => {
    const held = nextHold(idle, true, 0).state;
    const step = nextHold(held, false, 80);       // veri 80 ms'de geldi
    expect(step.timeoutIn).toBe(MIN_SPINNER_MS - 80);
  });

  it('hiç tutmuyorken koşul kapalıysa hiçbir şey yapmaz', () => {
    const step = nextHold(idle, false, 5000);
    expect(step.state).toBe(idle);
    expect(step.timeoutIn).toBeNull();
  });

  it('ikinci yükleme turunda sayaç yeniden başlar', () => {
    const first = nextHold(idle, true, 0).state;
    const done = nextHold(first, false, MIN_SPINNER_MS).state;
    expect(done.held).toBe(false);
    const second = nextHold(done, true, 9000).state;
    expect(second).toEqual({ held: true, startedAt: 9000 });
  });

  it('değişiklik yokken aynı nesneyi döndürür', () => {
    // Yeni nesne dönmek, durumu effect içinde güncelleyen çağıranda sonsuz
    // render döngüsü yaratıyor: "Maximum update depth exceeded".
    const held = nextHold(idle, true, 1000).state;
    expect(nextHold(held, true, 1200).state).toBe(held);
    expect(nextHold(held, true, 9999).state).toBe(held);
    const done = nextHold(held, false, 1000 + MIN_SPINNER_MS).state;
    expect(nextHold(done, false, 99999).state).toBe(done);
  });

  it('asgari süre çağrı başına ayarlanabilir', () => {
    const held = nextHold(idle, true, 0, 300).state;
    expect(nextHold(held, false, 100, 300).timeoutIn).toBe(200);
    expect(nextHold(held, false, 300, 300).state.held).toBe(false);
  });
});
