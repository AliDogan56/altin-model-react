import { BINANCE_WS } from '../config';

export type BinanceTick = { price: number; changePct: number };

/** PAXG/USDT 24s ticker. Tarayıcıdan doğrudan bağlanır, gateway'e uğramaz. */
export const subscribeBinance = (
  onTick: (tick: BinanceTick) => void,
  onOffline: () => void,
): (() => void) => {
  const stream = new WebSocket(BINANCE_WS);
  stream.onmessage = event => {
    const t = JSON.parse(event.data);
    const price = +t.c;
    if (!Number.isFinite(price)) return;
    onTick({ price, changePct: +t.P });
  };
  stream.onerror = onOffline;
  stream.onclose = onOffline;
  return () => stream.close();
};
