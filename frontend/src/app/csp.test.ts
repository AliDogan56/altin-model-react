import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * CSP ile kaynak arasındaki bağı korur. `nginx-security.conf` satır içi tema
 * betiğine hash ile izin verir; betik değişip hash güncellenmezse tarayıcı
 * betiği sessizce engeller — koyu tema seçen kullanıcı bir kare aydınlık ekran
 * görür ve kimse hata almaz. Bu test kırılırsa hash'i yeniden hesapla.
 */
const root = join(__dirname, '..', '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const csp = readFileSync(join(root, 'nginx-security.conf'), 'utf8');
const harem = readFileSync(join(root, 'src/services/config.ts'), 'utf8');

const inlineScripts = [...html.matchAll(/<script(?![^>]*\b(?:src|type)=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);

describe('CSP', () => {
  it('index.html tek bir satır içi betik taşır (tema damgası)', () => {
    expect(inlineScripts).toHaveLength(1);
    expect(inlineScripts[0]).toContain('oaa-theme');
  });

  it('satır içi betiğin sha256 hash\'i CSP\'de izinli', () => {
    const hash = createHash('sha256').update(inlineScripts[0], 'utf8').digest('base64');
    expect(csp).toContain(`'sha256-${hash}'`);
  });

  it('canlı fiyat soketinin adresi connect-src içinde', () => {
    const host = /wss?:\/\/([a-z0-9.-]+)/.exec(harem)?.[1];
    expect(host).toBeTruthy();
    const connect = /connect-src ([^;]+);/.exec(csp)?.[1] ?? '';
    expect(connect).toContain(`wss://${host}`);
  });

  it('iframe içine alınma kapalı', () => {
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toMatch(/X-Frame-Options "DENY"/);
  });
});
