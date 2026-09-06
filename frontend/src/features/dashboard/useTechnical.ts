import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchTechnical, type PivotMethod, type PivotPeriod, type SessionMeta, type Technical, type TechnicalParams } from '../../services/api/technical';
import type { SpotState } from '../../services/realtime/types';

/*
 * `GET /v1/market/xau/technical` tek kaynak: günlük seri, referans fiyat, pivot
 * merdiveni, bölgeler, göstergeler, trend, momentum ve kırılım hep bu yanıttan
 * okunur. Kanca yalnız **ne zaman** çekileceğini bilir; sayıların hiçbirini
 * hesaplamaz (merdiven marjı/ATR'si sunucuda, istemcide üretilmez).
 */

export type TechnicalStatus = 'loading' | 'live' | 'fallback';
export type TechnicalState = {
  /** Son başarılı yanıt. Yeni istek başarısız olursa **eski yanıt kalır**, durum `fallback` olur. */
  technical: Technical | null;
  status: TechnicalStatus;
  refresh: () => Promise<void>;
};

/** Sunucudaki saatlik job veri setini tazeliyor; sekme de arada bir yetişmeli. */
export const REFRESH_MS = 10 * 60 * 1000;
/** Bu süreden uzun gizli kalan sekme, görünür olur olmaz yeniden çeker. */
export const STALE_AFTER_MS = 5 * 60 * 1000;
/** Dönem/yöntem anahtarına art arda basılınca her basış ayrı istek atmasın. */
export const SETTINGS_DEBOUNCE_MS = 300;

export const isStale = (lastFetchedAt: number, now: number, staleAfter = STALE_AFTER_MS): boolean =>
  now - lastFetchedAt >= staleAfter;

/** Üst üste binen çağrıların "aynı istek" sayılıp sayılmayacağını belirler. */
export const paramsKey = (params: TechnicalParams): string => `${params.pivotMethod}:${params.pivotPeriod}`;

/**
 * Açılışta bir kez, sonra 10 dakikada bir ve uzun süre gizli kalmış sekme
 * yeniden görünür olunca `refresh` çağırır. Önceden `useMarketData` içinde
 * satır içiydi; teknik paket de aynı ritmi izlesin diye ayrıldı.
 */
export const useRefreshCadence = (refresh: () => Promise<void>, lastFetchedAt: { readonly current: number }): void => {
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, REFRESH_MS);
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return;
      if (!isStale(lastFetchedAt.current, Date.now())) return;
      void refresh();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [refresh, lastFetchedAt]);
};

/* --- teknik paket → panelin piyasa serileri ---------------------------------- */

/**
 * Grafiğin mum şekli: `date,h,l,c` + gövdenin diğer ucu `pc` (kaynakta açılış
 * yok; gövde tanımı sunucunun `daily.body_definition`'ı). Eski tarayıcı
 * gösterge modülü silindiği için tip burada tanımlı.
 */
export type MarketCandle = { date: string; h: number; l: number; c: number; pc: number | null };
export type MarketSeries = {
  history: [string, number][]; candles: MarketCandle[];
  /** Günlük kapanış: tahmin isteğinin `price`'ı buna bağlanır. */
  lastClose: number | null;
  /** Tüm teknik blokların ölçtüğü referans fiyat (gün içi son mum ya da günlük kapanış). */
  spot: SpotState;
};

const EMPTY: MarketSeries = { history: [], candles: [], lastClose: null, spot: { price: null, time: null, live: false } };

/**
 * Grafik ve göstergelerin beklediği seriler sunucu yanıtından türetilir; başka
 * hiçbir kaynak (pakete gömülü yedek, Harem soketi) bu serilere karışmaz.
 * Referans değeri yoksa **yerine sayı konmaz**: son mumun kapanışı başka bir
 * çerçevedir ve sessizce tahmin isteğine sızıyordu. Eksik değer `null` kalır,
 * kartlar `reference.status`'un cümlesini yazar.
 */
export const marketSeries = (technical: Technical | null): MarketSeries => {
  if (!technical) return EMPTY;
  const rows = technical.daily?.candles ?? [];
  const candles: MarketCandle[] = rows.map(row => ({ date: row.date, h: row.high, l: row.low, c: row.close, pc: row.prevClose }));
  const history: [string, number][] = rows.map(row => [row.date, row.close]);
  const reference = technical.reference;
  const price = reference.value;
  const time = reference.asOf ? new Date(reference.asOf)
    : reference.dailyDate ? new Date(`${reference.dailyDate}T00:00:00Z`) : null;
  return { history, candles, lastClose: reference.dailyClose, spot: { price, time, live: price != null } };
};

/** Açık seansta 15 dakikadan eski gün içi veri gecikmeli sayılır. */
export const SESSION_STALE_MS = 15 * 60 * 1000;
/** Piyasa kapalıyken (hafta sonu) referans meşru olarak son seanstır; üç gün tolerans. */
export const CLOSED_STALE_MS = 3 * 86400000;

/**
 * Seans verisinin "gecikmeli" eşiği tek yerden: sunucu `stale` diyorsa
 * anında (0 ms), piyasa kapalıysa üç gün, açıksa 15 dakika. Merdiven ve
 * momentum kartları aynı raydayken biri "gecikmeli" diğeri "son veri" diyordu.
 */
export const sessionStaleAfterMs = (meta: SessionMeta | null | undefined): number =>
  meta?.stale ? 0 : meta?.marketState === 'CLOSED' ? CLOSED_STALE_MS : SESSION_STALE_MS;

/* --- kanca ---------------------------------------------------------------------- */

type InFlight = { key: string; controller: AbortController; promise: Promise<void> };
const isAbort = (error: unknown): boolean => error instanceof Error && error.name === 'AbortError';

/**
 * Yanıt 27 pivot setinin tamamını taşır ama merdiven yalnız başlık için
 * gelir; dönem/yöntem değişince (300 ms tamponla) yeniden istenir ve yeni
 * yanıt gelene kadar **eski merdiven gösterilmeye devam eder**. Aynı
 * parametreyle üst üste gelen çağrılar süren isteğe biner; parametre
 * değişince süren istek iptal edilir — `fetchTechnical` iptali `null` değil
 * hata olarak yükselttiği için eski isteğin boşu yeni veriyi ezemez.
 */
export const useTechnical = ({ pivotMethod, pivotPeriod }: { pivotMethod: PivotMethod; pivotPeriod: PivotPeriod }): TechnicalState => {
  const [technical, setTechnical] = useState<Technical | null>(null);
  const [status, setStatus] = useState<TechnicalStatus>('loading');
  const params = useRef<TechnicalParams>({ pivotMethod, pivotPeriod });
  const lastFetchedAt = useRef(0);
  const inFlight = useRef<InFlight | null>(null);

  const abortInFlight = () => { inFlight.current?.controller.abort(); inFlight.current = null; };

  const load = useCallback((next: TechnicalParams): Promise<void> => {
    const key = paramsKey(next);
    if (inFlight.current?.key === key) return inFlight.current.promise;
    abortInFlight();
    const controller = new AbortController();
    setStatus('loading');
    const promise = (async () => {
      try {
        const result = await fetchTechnical(next, controller.signal);
        if (controller.signal.aborted) return;
        setTechnical(previous => result ?? previous);
        setStatus(result ? 'live' : 'fallback');
        lastFetchedAt.current = Date.now();
      } catch (error) {
        if (isAbort(error)) return;
        /* İstemci ağ/şema hatasını zaten `null`a çevirir; buraya düşen hata
           beklenmedik. Kartlar eski veriyle kalsın, durum "erişilemiyor" desin. */
        setStatus('fallback');
        lastFetchedAt.current = Date.now();
      } finally {
        if (inFlight.current?.controller === controller) inFlight.current = null;
      }
    })();
    inFlight.current = { key, controller, promise };
    return promise;
  }, []);

  const refresh = useCallback(() => load(params.current), [load]);
  /* Sıra önemli: açılış isteği burada başlar, aşağıdaki ayar etkisi ilk
     çalışmasında aynı anahtarı süren istekte görüp ikinci istek atmaz. */
  useRefreshCadence(refresh, lastFetchedAt);
  useEffect(() => () => abortInFlight(), []);

  useEffect(() => {
    const next: TechnicalParams = { pivotMethod, pivotPeriod };
    params.current = next;
    if (inFlight.current?.key === paramsKey(next)) return;
    const timer = window.setTimeout(() => { void load(next); }, SETTINGS_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [pivotMethod, pivotPeriod, load]);

  return useMemo(() => ({ technical, status, refresh }), [technical, status, refresh]);
};
