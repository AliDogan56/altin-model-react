import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FeatureMap } from '../../domain/model/types';
import { fetchNews, type NewsArticle } from '../../services/api/market';
import type { Momentum } from '../../services/api/momentum';
import { fetchLatestFeatures } from '../../services/api/model';
import { fetchScorecard, type Scorecard } from '../../services/api/metrics';
import type { Technical } from '../../services/api/technical';
import { subscribeHarem } from '../../services/realtime/harem';
import type { Quote, RateState, SpotState } from '../../services/realtime/types';
import { marketSeries, useRefreshCadence, type MarketCandle } from './useTechnical';

/** `busy`: bir çekim sürüyor — panel başlığında spinner bunu gösterir. */
export type Status = { type: 'ok' | 'warn'; text: string; busy?: boolean };

/** Bu kancanın kendi REST kaynakları: model girdileri ve bülten. Fiyat serisi teknik paketten gelir. */
const SOURCES = 2;

export type MarketData = {
  live: FeatureMap; lastClose: number | null;
  history: [string, number][]; candles: MarketCandle[]; news: NewsArticle[];
  /** Gün içi seans momentumu; teknik paketin `session` bloğu. Gün içi veri yokken null. */
  momentum: Momentum | null;
  status: Status;
  /** Teknik paketin referans fiyatı; Harem kotasyonu **buraya yazılmaz** (`harem` ayrı). */
  spot: SpotState; harem: RateState; usdTry: RateState;
  ziynet: Record<string, Quote>;
  /** Modelin katman dışı karnesi; servis erişilemezse null. */
  scorecard: Scorecard | null;
  /** Girdilerin ait olduğu veri seti tarihi. */
  featuresDate: string | null;
  refresh: () => Promise<void>;
};

/**
 * Piyasa verisi tek yerde toplanır. Fiyat serisi, günlük kapanış ve referans
 * fiyat `useTechnical`'ın yanıtından türetilir (pakete gömülü yedek seri ve
 * `/v1/market/xau` çağrısı kalktı); model girdileri, karne ve bülten REST ile,
 * ziynet/USDTRY/Harem ons kotasyonu soketle gelir ve yalnız gösterim içindir.
 */
export const useMarketData = (technical: Technical | null): MarketData => {
  const [live, setLive] = useState<FeatureMap>({});
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [status, setStatus] = useState<Status>({ type: 'warn', text: 'Canlı veriler bekleniyor', busy: true });
  const [harem, setHarem] = useState<RateState>({ alis: null, satis: null, time: null, live: false });
  const [usdTry, setUsdTry] = useState<RateState>({ alis: null, satis: null, time: null, live: false });
  const [ziynet, setZiynet] = useState<Record<string, Quote>>({});
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [featuresDate, setFeaturesDate] = useState<string | null>(null);

  const { history, candles, lastClose, spot } = useMemo(() => marketSeries(technical), [technical]);
  const momentum = technical?.session ?? null;

  const running = useRef(false);
  const lastFetchedAt = useRef(0);

  const refresh = useCallback(async () => {
    if (running.current) return;          // üst üste binen çağrılar veriyi karıştırıyordu
    running.current = true;
    setStatus({ type: 'warn', text: 'Canlı veriler alınıyor…', busy: true });
    const next: FeatureMap = {};

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

    const settled = await Promise.allSettled([inputs, headlines]);
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
  useRefreshCadence(refresh, lastFetchedAt);

  useEffect(() => subscribeHarem(
    update => {
      if (Object.keys(update.quotes).length) setZiynet(prev => ({ ...prev, ...update.quotes }));
      if (update.ons) setHarem({ ...update.ons, time: new Date(), live: true });
      if (update.usdTry) setUsdTry({ ...update.usdTry, time: new Date(), live: true });
    },
    () => { setHarem(h => ({ ...h, live: false })); setUsdTry(r => ({ ...r, live: false })); },
  ), []);

  return useMemo(
    () => ({ live, lastClose, history, candles, news, momentum, status, spot, harem, usdTry, ziynet, scorecard, featuresDate, refresh }),
    [live, lastClose, history, candles, news, momentum, status, spot, harem, usdTry, ziynet, scorecard, featuresDate, refresh]);
};
