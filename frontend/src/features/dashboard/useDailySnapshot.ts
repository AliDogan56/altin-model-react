import { useEffect, useRef } from 'react';
import type { FeatureMap } from '../../domain/model/types';
import { postSnapshot } from '../../services/api/model';
import type { RateState, SpotState } from '../../services/realtime/types';

const istanbulDay = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Europe/Istanbul' });

/** Günde bir gözlem kaydı. Gün anahtarı Europe/Istanbul'a göre alınır ve
 *  `pending:` işaretiyle tekilleştirilir; istek uçarken ikinci tetikleme gelmesin. */
export const useDailySnapshot = (spot: SpotState, harem: RateState, features: FeatureMap) => {
  const sent = useRef('');
  useEffect(() => {
    if (!spot.live || !harem.live || !harem.satis) return;
    const day = istanbulDay();
    if (sent.current === day || sent.current === `pending:${day}`) return;
    sent.current = `pending:${day}`;
    postSnapshot({
      model_price: spot.price, display_price: harem.satis, features,
      observed_at: new Date().toISOString(), source: 'PAXG/USDT', display_source: 'ONS/XAUUSD',
    })
      .then(response => { sent.current = response.ok ? day : ''; })
      .catch(() => { sent.current = ''; });
  }, [spot.live, spot.price, harem.live, harem.satis, features]);
};
