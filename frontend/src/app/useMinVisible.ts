import { useEffect, useRef, useState } from 'react';
import { MIN_SPINNER_MS, nextHold, type HoldState } from '../lib/hold';

export { MIN_SPINNER_MS };

/**
 * Bir yükleme durumunu en az `ms` kadar ekranda tutar.
 *
 * Karar mantığı `lib/hold.ts` içinde saf ve test edilebilir; bu kanca yalnız
 * onu React durumuna ve zamanlayıcıya bağlar.
 */
export const useMinVisible = (active: boolean, ms: number = MIN_SPINNER_MS): boolean => {
  const [state, setState] = useState<HoldState>(() => ({ held: active, startedAt: Date.now() }));
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    window.clearTimeout(timer.current);
    const step = nextHold(state, active, Date.now(), ms);
    if (step.state !== state) setState(step.state);
    if (step.timeoutIn !== null) {
      timer.current = window.setTimeout(
        () => setState(current => nextHold(current, false, Date.now(), ms).state),
        step.timeoutIn,
      );
    }
  }, [active, state, ms]);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  return state.held;
};
