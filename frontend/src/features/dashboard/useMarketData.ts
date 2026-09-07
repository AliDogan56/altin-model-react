import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { model } from '../../data/artifact';
import type { Candle } from '../../domain/indicators';
import type { FeatureMap } from '../../domain/model/types';
import { fetchNews, fetchXauHistory, type NewsArticle } from '../../services/api/market';
import { fetchMomentum, type Momentum } from '../../services/api/momentum';
import { fetchLatestFeatures } from '../../services/api/model';
import { fetchScorecard, type Scorecard } from '../../services/api/metrics';
import { subscribeHarem } from '../../services/realtime/harem';
import type { Quote, RateState, SpotState, Tick } from '../../services/realtime/types';

/** `busy`: bir çekim sürüyor — panel başlığında spinner bunu gösterir. */
export type Status = { type: 'ok' | 'warn'; text: string; busy?: boolean };

const SOURCES = 3;
/** Sunucudaki saatlik job veri setini tazeliyor; sekme de arada bir yetişmeli. */
const REFRESH_MS = 10 * 60 * 1000;
/** Bu süreden uzun gizli kalan sekme, görünür olur olmaz yeniden çeker. */
const STALE_AFTER_MS = 5 * 60 * 1000;

export type MarketData = {
  live: FeatureMap; lastClose: number | null;
  history: [string, number][]; candles: Candle[]; news: NewsArticle[];
  momentum: Momentum | null;
  status: Status; spot: SpotState; harem: RateState; usdTry: RateState;
  ziynet: Record<string, Quote>; haremTicks: Tick[];
  /** Modelin katman dışı karnesi; servis erişilemezse null. */
  scorecard: Scorecard | null;
  /** Girdilerin ait olduğu veri seti tarihi. */
  featuresDate: string | null;
  refresh: () => Promise<void>;
};

/** Tüm piyasa verisi tek yerde toplanır: REST ile açılış anlık görüntüsü,
 *  ardından Harem ONS soketiyle canlı XAU/USD akışı. */
export const useMarketData = (): MarketData => {
  const [live, setLive] = useState<FeatureMap>({});
  const [lastClose, setLastClose] = useState<number | null>(null);
  const [history, setHistory] = useState<[string, number][]>(model.history);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [status, setStatus] = useState<Status>({ type: 'warn', text: 'Canlı veriler bekleniyor', busy: true });
  const [spot, setSpot] = useState<SpotState>({ price: model.latestPrice, change: 0, secondChange: 0, time: null, live: false });
  const [harem, setHarem] = useState<RateState>({ alis: null, satis: null, time: null, live: false });
  const [usdTry, setUsdTry] = useState<RateState>({ alis: null, satis: null, time: null, live: false });
  const [ziynet, setZiynet] = useState<Record<string, Quote>>({});
  const [haremTicks, setHaremTicks] = useState<Tick[]>([]);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [featuresDate, setFeaturesDate] = useState<string | null>(null);
  /* Gün içi momentum; 5 dakikalık mumlardan hesaplanır, piyasa servisinden gelir. */
  const [momentum, setMomentum] = useState<Momentum | null>(null);

  const running = useRef(false);
  const lastFetchedAt = useRef(0);

  const refresh = useCallback(async () => {
    if (running.current) return;          // üst üste binen çağrılar veriyi karıştırıyordu
    running.current = true;
    setStatus({ type: 'warn', text: 'Canlı veriler alınıyor…', busy: true });
    const next: FeatureMap = {};

    const gold = (async () => {
      const points = await fetchXauHistory();
      const close = points.map(v => +v.c);
      setCandles(points.map(v => ({ date: v.d, h: +v.h, l: +v.l, c: +v.c })));
      setHistory(points.map(v => [v.d, +v.c]));
      setLastClose(close[close.length - 1]);
      const previous = close.at(-2) || close.at(-1)!;
      const current = close.at(-1)!;
      setSpot({ price: current, change: (current / previous - 1) * 100, secondChange: 0,
        time: new Date(`${points.at(-1)!.d}T00:00:00Z`), live: true });
    })();

    /* Model girdileri servisten alınır: eğitim setiyle birebir aynı formül.
       Tarayıcı FRED serilerini artık hiç indirmiyor. */
    const inputs = (async () => {
      const latest = await fetchLatestFeatures();
      Object.assign(next, latest.features);
      setFeaturesDate(latest.date);
    })();
    /* Karne artefakttan değil servisten gelir; tarayıcıdaki nötr yedek onu üretemiyordu. */
    const karne = fetchScorecard().then(setScorecard).catch(() => setScorecard(null));
    const headlines = fetchNews().then(setNews);
    /* Seans yeni başladıysa servis 503 verir; bu arıza değil, veri henüz
       yetmiyor demektir. Bölüm o an gizlenir. */
    const pulse = fetchMomentum().then(setMomentum).catch(() => setMomentum(null));

    await pulse;
    const settled = await Promise.allSettled([gold, inputs, headlines]);
    await karne;
    setLive(v => ({ ...v, ...next }));
    const ok = settled.filter(x => x.status === 'fulfilled').length;
    setStatus(ok === SOURCES
      ? { type: 'ok', text: `Canlı · ${new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}` }
      : { type: 'warn', text: `Kısmi canlı · ${ok}/${SOURCES} kaynak` });
    lastFetchedAt.current = Date.now();
    running.current = false;
  }, []);

  /* Veriler yalnız sayfa açılışında çekiliyordu: gün boyu açık kalan bir sekme
     bayat girdilerle tahmin gösteriyordu. Artık periyodik olarak ve sekme
     yeniden görünür olduğunda tazelenir. */
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, REFRESH_MS);
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return;
      if (Date.now() - lastFetchedAt.current < STALE_AFTER_MS) return;
      void refresh();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [refresh]);

  useEffect(() => subscribeHarem(
    update => {
      if (Object.keys(update.quotes).length) setZiynet(prev => ({ ...prev, ...update.quotes }));
      if (update.ons) {
        setHarem({ ...update.ons, time: new Date(), live: true });
        setSpot(previous => ({ ...previous, price: update.ons!.satis, time: new Date(), live: true }));
        setHaremTicks(t => [...t.slice(-89), { time: Date.now(), price: update.ons!.satis }]);
      }
      if (update.usdTry) setUsdTry({ ...update.usdTry, time: new Date(), live: true });
    },
    () => { setHarem(h => ({ ...h, live: false })); setUsdTry(r => ({ ...r, live: false })); },
  ), []);

  return useMemo(
    () => ({ live, lastClose, history, candles, news, momentum, status, spot, harem, usdTry, ziynet, haremTicks, scorecard, featuresDate, refresh }),
    [live, lastClose, history, candles, news, momentum, status, spot, harem, usdTry, ziynet, haremTicks, scorecard, featuresDate, refresh]);
};
