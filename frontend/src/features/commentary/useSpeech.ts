import { useCallback, useEffect, useRef, useState } from 'react';
import { pickTurkishVoice, speechSupported, type SpeechChunk } from './speech';

export type SpeechState = 'idle' | 'speaking' | 'paused';

/**
 * Parçaları sırayla okur; `current` okunan parçanın anahtarı (vurgulama için).
 * Pencere kapanınca ya da bileşen ayrılınca susturur. iOS'ta ilk `speak` bir
 * kullanıcı dokunuşuyla gelmeli — düğmeden çağrıldığı için sağlanır.
 */
export const useSpeech = (chunks: SpeechChunk[]) => {
  const supported = speechSupported();
  const [state, setState] = useState<SpeechState>('idle');
  const [current, setCurrent] = useState<string | null>(null);
  const queue = useRef<SpeechChunk[]>([]);
  const token = useRef(0);

  const stop = useCallback(() => {
    token.current += 1; queue.current = [];
    if (supported) window.speechSynthesis.cancel();
    setState('idle'); setCurrent(null);
  }, [supported]);

  const speakNext = useCallback((run: number) => {
    const chunk = queue.current.shift();
    if (!chunk || run !== token.current) { if (run === token.current) { setState('idle'); setCurrent(null); } return; }
    const utterance = new SpeechSynthesisUtterance(chunk.text);
    utterance.lang = 'tr-TR'; utterance.rate = 1;
    const voice = pickTurkishVoice(window.speechSynthesis.getVoices());
    if (voice) utterance.voice = voice;
    utterance.onstart = () => { if (run === token.current) setCurrent(chunk.key); };
    utterance.onend = () => speakNext(run);
    utterance.onerror = event => { if (event.error !== 'interrupted' && event.error !== 'canceled') speakNext(run); };
    window.speechSynthesis.speak(utterance);
  }, []);

  const play = useCallback(() => {
    if (!supported) return;
    if (state === 'paused') { window.speechSynthesis.resume(); setState('speaking'); return; }
    window.speechSynthesis.cancel();
    token.current += 1; const run = token.current;
    queue.current = [...chunks]; setState('speaking');
    // Sesler bazı tarayıcılarda ilk çağrıda boş gelir; liste dolunca tekrar denemek gerekmez, utterance dil bilgisiyle konuşur.
    speakNext(run);
  }, [supported, state, chunks, speakNext]);

  const pause = useCallback(() => { if (supported && state === 'speaking') { window.speechSynthesis.pause(); setState('paused'); } }, [supported, state]);

  useEffect(() => () => { if (supported) window.speechSynthesis.cancel(); }, [supported]);
  return { supported, state, current, play, pause, stop };
};
