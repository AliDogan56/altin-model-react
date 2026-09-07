import { useCallback, useState } from 'react';
import { applySlot, readStoredSlots, storeSlots } from './tickerOptions';

/** Başlık kartının üç seçilebilir yuvası; seçim tarayıcıda saklanır. */
export const useTickerSlots = () => {
  const [slots, setSlots] = useState<string[]>(readStoredSlots);
  const setSlot = useCallback((index: number, id: string) => {
    setSlots(current => { const next = applySlot(current, index, id); storeSlots(next); return next; });
  }, []);
  return { slots, setSlot };
};
