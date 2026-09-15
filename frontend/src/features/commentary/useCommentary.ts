import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchCommentary, type Commentary } from '../../services/api/commentary';
import { SEEN_AT_KEY, isUnread, readSeenAt, writeSeenAt } from './unread';

export type CommentaryStatus = 'loading' | 'ready' | 'pending' | 'error';
/** 2 dakikada bir `If-None-Match` ile yoklama: değişmemişse 304, gövde yok. Yeni yorum 1–4 saatte bir gelir. */
export const POLL_MS = 2 * 60 * 1000;

/**
 * Son yorumu tutar; "yeni" kararı `unread.ts`: yorumun üretim zamanı, son görülen yorumun üretim
 * zamanından büyükse yeni. Sayfa açıkken yeni sürüm gelirse `arrived` bir kez dolar (balon için).
 */
export const useCommentary = (initial: Commentary | null = null) => {
  /* `initial`: /yorum sayfasının HTML'ine gömülü yorum (sunucu SSI ile basar); organik inişte
     ilk render metinle başlar, ağ isteği yalnız tazeler. */
  const [status, setStatus] = useState<CommentaryStatus>(initial ? 'ready' : 'loading');
  const [data, setData] = useState<Commentary | null>(initial);
  const [seenAt, setSeenAt] = useState<string | null>(readSeenAt);
  const [arrived, setArrived] = useState<string | null>(null);   // sayfa açıkken gelen yeni sürüm
  const inflight = useRef<AbortController | null>(null);
  const etag = useRef<string | null>(null);
  const known = useRef<string | null>(initial?.version ?? null);

  const refresh = useCallback(async () => {
    inflight.current?.abort();
    const controller = new AbortController(); inflight.current = controller;
    try {
      const result = await fetchCommentary(controller.signal, etag.current);
      if (controller.signal.aborted) return;
      if (result.kind === 'unchanged') return;
      if (result.kind === 'ready') {
        etag.current = result.etag;
        if (known.current && known.current !== result.data.version) setArrived(result.data.version);
        known.current = result.data.version;
        setData(result.data); setStatus('ready');
      } else setStatus('pending');
    } catch {
      if (controller.signal.aborted) return;
      setStatus(current => current === 'ready' ? current : 'error');   // eski yorum eldeyse onu göstermeye devam et
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, POLL_MS);
    const onVisible = () => { if (document.visibilityState === 'visible') void refresh(); };
    const onStorage = (event: StorageEvent) => { if (event.key === SEEN_AT_KEY) setSeenAt(event.newValue); };   // diğer sekmede okundu
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('storage', onStorage);
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', onVisible); window.removeEventListener('storage', onStorage); inflight.current?.abort(); };
  }, [refresh]);

  const markSeen = useCallback(() => {
    if (!data?.generatedAt) return;
    writeSeenAt(data.generatedAt); setSeenAt(data.generatedAt); setArrived(null);
  }, [data]);
  const dismissArrived = useCallback(() => setArrived(null), []);
  const unread = status === 'ready' && data != null && isUnread(data.generatedAt, seenAt);
  return { status, data, unread, arrived, refresh, markSeen, dismissArrived };
};
