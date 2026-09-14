/**
 * Yorumun sesli okunması: tarayıcının kendi sentezleyicisi (`speechSynthesis`),
 * sunucu yok. Türkçe ses cihazda ne varsa o; yoksa varsayılan ses `tr-TR` diliyle
 * çalışır. Metin bölüm bölüm okunur: uzun tek bir cümle dizisi bazı tarayıcılarda
 * 15 sn sonra sessizce kesiliyor, parça parça vermek hem bunu önler hem de okunan
 * bölümün vurgulanmasını sağlar. Saf kısım (parçalama, ses seçimi) test edilir.
 */
import type { Commentary } from '../../services/api/commentary';

export type SpeechChunk = { key: string; text: string };

export const speechChunks = (data: Commentary): SpeechChunk[] => [
  { key: 'headline', text: data.headline },
  { key: 'summary', text: data.summary },
  ...data.sections.map(s => ({ key: s.id, text: `${s.title}. ${s.text}` })),
];

/** Türkçe ses: önce `tr-TR`, sonra `tr` ile başlayan; yerel (cihaz) sesler öne alınır. */
export const pickTurkishVoice = (voices: readonly SpeechSynthesisVoice[]): SpeechSynthesisVoice | null => {
  const turkish = voices.filter(v => /^tr([-_]|$)/i.test(v.lang));
  if (!turkish.length) return null;
  return turkish.find(v => v.localService && /^tr[-_]TR$/i.test(v.lang)) ?? turkish.find(v => /^tr[-_]TR$/i.test(v.lang)) ?? turkish[0];
};

export const speechSupported = (): boolean =>
  typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined';
