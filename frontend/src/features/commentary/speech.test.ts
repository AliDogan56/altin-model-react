import { describe, expect, it } from 'vitest';
import { pickTurkishVoice, speechChunks } from './speech';

const voice = (lang: string, localService = true, name = lang) => ({ lang, localService, name, default: false, voiceURI: name }) as SpeechSynthesisVoice;
const data = { version: 'v', asOf: '', generatedAt: '', ageSeconds: null, runMode: 'full', triggerReason: null, live: null, officialFix: null, narration: null,
  title: 'T', headline: 'Manşet.', summary: 'Özet.', sections: [{ id: 'giris', title: 'Giriş', text: 'Metin.' }], disclaimer: 'D' };

describe('sesli okuma', () => {
  it('parçalar manşet, özet ve bölümler sırasıyla; bölüm başlığı metne eklenir', () => {
    expect(speechChunks(data)).toEqual([{ key: 'headline', text: 'Manşet.' }, { key: 'summary', text: 'Özet.' }, { key: 'giris', text: 'Giriş. Metin.' }]);
  });
  it('Türkçe ses seçimi: yerel tr-TR > uzak tr-TR > başka tr > yok', () => {
    expect(pickTurkishVoice([voice('en-US')])).toBeNull();
    expect(pickTurkishVoice([voice('en-US'), voice('tr', true, 'tr-generic'), voice('tr-TR', false, 'remote'), voice('tr-TR', true, 'local')])!.name).toBe('local');
    expect(pickTurkishVoice([voice('tr', true, 'tr-generic'), voice('tr-TR', false, 'remote')])!.name).toBe('remote');
    expect(pickTurkishVoice([voice('tr_TR', true, 'alt')])!.name).toBe('alt');
    expect(pickTurkishVoice([])).toBeNull();
  });
});
