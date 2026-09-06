import { describe, expect, it } from 'vitest';
import html from '../../index.html?raw';
import csp from '../../nginx-security.conf?raw';
import config from '../services/config.ts?raw';

/**
 * CSP ile kaynak arasındaki bağı korur. `nginx-security.conf` satır içi tema
 * betiğine hash ile izin verir; betik değişip hash güncellenmezse tarayıcı
 * betiği sessizce engeller — koyu tema seçen kullanıcı bir kare aydınlık ekran
 * görür ve kimse hata almaz. Bu test kırılırsa hash'i yeniden hesapla.
 *
 * Dosyalar Vite'ın `?raw` içe aktarımıyla okunur: `node:fs` kullanılsaydı
 * `tsc` (Node tipleri projede yok) kırılırdı; vitest ikisini de çözer.
 */
const inlineScripts = [...html.matchAll(/<script(?![^>]*\b(?:src|type)=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);

const sha256 = async (text: string): Promise<string> => {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return btoa(String.fromCharCode(...new Uint8Array(digest)));
};

describe('CSP', () => {
  it('index.html tek bir satır içi betik taşır (tema damgası)', () => {
    expect(inlineScripts).toHaveLength(1);
    expect(inlineScripts[0]).toContain('oaa-theme');
  });

  it('satır içi betiğin sha256 hash\'i CSP\'de izinli', async () => {
    expect(csp).toContain(`'sha256-${await sha256(inlineScripts[0])}'`);
  });

  it('canlı fiyat soketinin adresi connect-src içinde', () => {
    const host = /wss?:\/\/([a-z0-9.-]+)/.exec(config)?.[1];
    expect(host).toBeTruthy();
    const connect = /connect-src ([^;]+);/.exec(csp)?.[1] ?? '';
    expect(connect).toContain(`wss://${host}`);
  });

  it('iframe içine alınma kapalı', () => {
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toMatch(/X-Frame-Options "DENY"/);
  });
});
