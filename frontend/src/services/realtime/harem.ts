import { io } from 'socket.io-client';
import { HAREM_WS } from '../config';
import type { Quote } from './types';

/** Socket kod -> etiket. Kotasyonlar doğrudan piyasadan gelir; ons üzerinden
 *  hesaplanan ham madde değeri işçilik ve marjı içermiyordu. */
export const ZIYNET: [string, string][] = [
  ['ALTIN', 'Gram altın'], ['AYAR22', '22 ayar gram'], ['CEYREK_YENI', 'Çeyrek (yeni)'],
  ['YARIM_YENI', 'Yarım (yeni)'], ['TEK_YENI', 'Tam (yeni)'], ['ATA_YENI', 'Yeni Ata'],
];

export type HaremPair = { alis: number; satis: number };

export type HaremUpdate = {
  quotes: Record<string, Quote>;
  ons: HaremPair | null;
  usdTry: HaremPair | null;
};

const pair = (row: Record<string, unknown> | undefined): HaremPair | null => {
  if (!row) return null;
  const alis = +(row.alis as number), satis = +(row.satis as number);
  return Number.isFinite(alis) && Number.isFinite(satis) ? { alis, satis } : null;
};

/** Payload'daki her ziynet kodunu tek seferde çıkarır; ham socket şekli dışarı sızmaz. */
export const readHaremPayload = (payload: unknown): HaremUpdate => {
  const data = ((payload as { data?: Record<string, never> })?.data || {}) as Record<string, Record<string, unknown>>;
  const quotes: Record<string, Quote> = {};
  ZIYNET.forEach(([code]) => {
    const row = data[code];
    const p = pair(row);
    if (!p || p.satis <= 0) return;
    quotes[code] = {
      ...p,
      dir: (row.dir as { satis_dir?: string })?.satis_dir || '',
      low: +(row.dusuk as number) || 0,
      high: +(row.yuksek as number) || 0,
      prev: +(row.kapanis as number) || 0,
      time: String(row.tarih || '').slice(-8),
    };
  });
  return { quotes, ons: pair(data.ONS), usdTry: pair(data.USDTRY || data.USD) };
};

export const subscribeHarem = (
  onUpdate: (update: HaremUpdate) => void,
  onOffline: () => void,
): (() => void) => {
  const socket = io(HAREM_WS, { transports: ['websocket'], reconnection: true, reconnectionDelay: 1000 });
  socket.on('price_changed', payload => onUpdate(readHaremPayload(payload)));
  socket.on('disconnect', onOffline);
  socket.on('connect_error', onOffline);
  return () => { socket.disconnect(); };
};
