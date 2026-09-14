import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchCommentary, type Commentary } from '../../services/api/commentary';

export type CommentaryStatus = 'loading' | 'ready' | 'pending' | 'error';
const REFRESH_MS = 10 * 60 * 1000;
const SEEN_KEY = 'oaa-commentary-seen';

const readSeen = (): string | null => { try { return window.localStorage.getItem(SEEN_KEY); } catch { return null; } };
const writeSeen = (version: string): void => { try { window.localStorage.setItem(SEEN_KEY, version); } catch { /* depolama yoksa rozet oturumla sınırlı */ } };

/** Son yorumu 10 dakikada bir ve pencere açılınca tazeler; okunmamış sürüm rozeti tarayıcıda saklanır. */
export const useCommentary = () => {
  const [status, setStatus] = useState<CommentaryStatus>('loading');
  const [data, setData] = useState<Commentary | null>(null);
  const [seen, setSeen] = useState<string | null>(readSeen);
  const inflight = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    inflight.current?.abort();
    const controller = new AbortController(); inflight.current = controller;
    try {
      const result = await fetchCommentary(controller.signal);
      if (controller.signal.aborted) return;
      if (result.kind === 'ready') { setData(result.data); setStatus('ready'); } else setStatus('pending');
    } catch (error) {
      if (controller.signal.aborted) return;
      setStatus(current => current === 'ready' ? current : 'error');   // eski yorum eldeyse onu göstermeye devam et
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, REFRESH_MS);
    return () => { window.clearInterval(timer); inflight.current?.abort(); };
  }, [refresh]);

  const markSeen = useCallback(() => { if (data) { writeSeen(data.version); setSeen(data.version); } }, [data]);
  const unread = status === 'ready' && data != null && seen !== data.version;
  return { status, data, unread, refresh, markSeen };
};
