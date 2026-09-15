import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { commentaryAudioUrl, type Narration } from '../../services/api/commentary';
import type { SpeechState } from './useSpeech';

/**
 * Sunucuda üretilmiş anlatıcı sesini (`/latest/audio`) çalar; `current` o anda okunan
 * bölümün anahtarı (bölüm zamanları sunucudan, tahmini). Ses alınamazsa `failed` olur ve
 * pencere tarayıcı sentezleyicisine düşer — düğme hiç kaybolmaz.
 */
export const useNarration = (version: string | null, narration: Narration | null) => {
  const [state, setState] = useState<SpeechState | 'loading'>('idle');
  const [time, setTime] = useState(0);
  const [failed, setFailed] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const available = !!version && !!narration && !failed;
  const url = useMemo(() => (version && narration ? commentaryAudioUrl(version) : null), [version, narration]);

  useEffect(() => {
    // Sürüm değişince eski ses durur ve öğe atılır; yeni ses ilk "Dinle"de kurulur.
    audio.current?.pause(); audio.current = null; setState('idle'); setTime(0); setFailed(false);
  }, [url]);
  useEffect(() => () => { audio.current?.pause(); audio.current = null; }, []);

  const ensure = useCallback((): HTMLAudioElement | null => {
    if (!url) return null;
    if (audio.current) return audio.current;
    const el = new Audio(url); el.preload = 'auto';
    el.addEventListener('timeupdate', () => setTime(el.currentTime));
    el.addEventListener('playing', () => setState('speaking'));
    el.addEventListener('waiting', () => setState('loading'));
    el.addEventListener('pause', () => { if (!el.ended) setState(current => current === 'idle' ? current : 'paused'); });
    el.addEventListener('ended', () => { setState('idle'); setTime(0); });
    el.addEventListener('error', () => { setFailed(true); setState('idle'); });
    audio.current = el;
    return el;
  }, [url]);

  const play = useCallback(() => {
    const el = ensure(); if (!el) return;
    setState('loading');
    el.play().catch(() => { setFailed(true); setState('idle'); });
  }, [ensure]);
  const pause = useCallback(() => { audio.current?.pause(); }, []);
  const stop = useCallback(() => { const el = audio.current; if (el) { el.pause(); el.currentTime = 0; } setState('idle'); setTime(0); }, []);

  const current = useMemo(() => {
    if (state === 'idle' || !narration) return null;
    return narration.segments.find(s => time >= s.start && time < s.end)?.id ?? null;
  }, [state, time, narration]);

  return { available, state, current, play, pause, stop, failed };
};
