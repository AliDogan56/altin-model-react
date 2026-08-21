import { useCallback, useEffect, useRef, useState } from 'react';
import { model } from '../../data/artifact';
import { goldFeatures } from '../../domain/market/goldFeatures';
import { FRED_IDS, macroFeatures } from '../../domain/market/macroFeatures';
import type { Candle } from '../../domain/indicators';
import type { FeatureMap } from '../../domain/model/types';
import {
  fetchFredSet, fetchKlines, fetchNews, fetchSpot, toCandles, toHistory, type NewsArticle,
} from '../../services/api/market';
import { subscribeBinance } from '../../services/realtime/binance';
import { subscribeHarem } from '../../services/realtime/harem';
import type { Quote, RateState, SpotState, Tick } from '../../services/realtime/types';

export type Status = { type: 'ok' | 'warn'; text: string };

const SOURCES = 3;

export type MarketData = {
  live: FeatureMap; lastClose: number | null;
  history: [string, number][]; candles: Candle[]; news: NewsArticle[];
  status: Status; spot: SpotState; harem: RateState; usdTry: RateState;
  ziynet: Record<string, Quote>; haremTicks: Tick[];
  refresh: () => Promise<void>;
};

/** Tüm piyasa verisi tek yerde toplanır: REST ile açılış anlık görüntüsü,
 *  ardından Binance ve Harem soketleriyle canlı akış. */
export const useMarketData = (): MarketData => {
  const [live, setLive] = useState<FeatureMap>({});
  const [lastClose, setLastClose] = useState<number | null>(null);
  const [history, setHistory] = useState<[string, number][]>(model.history);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [status, setStatus] = useState<Status>({ type: 'warn', text: 'Canlı veriler bekleniyor' });
  const [spot, setSpot] = useState<SpotState>({ price: model.latestPrice, change: 0, secondChange: 0, time: null, live: false });
  const [harem, setHarem] = useState<RateState>({ alis: null, satis: null, time: null, live: false });
  const [usdTry, setUsdTry] = useState<RateState>({ alis: null, satis: null, time: null, live: false });
  const [ziynet, setZiynet] = useState<Record<string, Quote>>({});
  const [haremTicks, setHaremTicks] = useState<Tick[]>([]);

  const refresh = useCallback(async () => {
    setStatus({ type: 'warn', text: 'Canlı veriler alınıyor…' });
    const next: FeatureMap = {};

    const gold = (async () => {
      const klines = await fetchKlines();
      const close = klines.map(v => +v[4]);
      Object.assign(next, goldFeatures({
        close, high: klines.map(v => +v[2]), low: klines.map(v => +v[3]), volume: klines.map(v => +v[5]),
      }));
      setCandles(toCandles(klines));
      setHistory(toHistory(klines));
      setLastClose(close[close.length - 1]);
    })();

    const macro = (async () => { Object.assign(next, macroFeatures(await fetchFredSet(FRED_IDS))); })();
    const headlines = fetchNews().then(setNews);

    const settled = await Promise.allSettled([gold, macro, headlines]);
    setLive(v => ({ ...v, ...next }));
    const ok = settled.filter(x => x.status === 'fulfilled').length;
    setStatus(ok === SOURCES
      ? { type: 'ok', text: `Canlı · ${new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}` }
      : { type: 'warn', text: `Kısmi canlı · ${ok}/${SOURCES} kaynak` });
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Soket bağlanana kadar boş kalmasın diye 24s ticker'dan açılış değeri.
  const booted = useRef(false);
  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    let active = true;
    fetchSpot()
      .then(d => { if (active) setSpot(s => ({ ...s, price: +d.lastPrice, change: +d.priceChangePercent, time: new Date(), live: true })); })
      .catch(() => {});
    return () => { active = false; };
  }, []);

  useEffect(() => subscribeBinance(
    tick => setSpot({ price: tick.price, change: tick.changePct, secondChange: 0, time: new Date(), live: true }),
    () => setSpot(s => ({ ...s, live: false })),
  ), []);

  useEffect(() => subscribeHarem(
    update => {
      if (Object.keys(update.quotes).length) setZiynet(prev => ({ ...prev, ...update.quotes }));
      if (update.ons) {
        setHarem({ ...update.ons, time: new Date(), live: true });
        setHaremTicks(t => [...t.slice(-89), { time: Date.now(), price: update.ons!.satis }]);
      }
      if (update.usdTry) setUsdTry({ ...update.usdTry, time: new Date(), live: true });
    },
    () => { setHarem(h => ({ ...h, live: false })); setUsdTry(r => ({ ...r, live: false })); },
  ), []);

  return { live, lastClose, history, candles, news, status, spot, harem, usdTry, ziynet, haremTicks, refresh };
};
