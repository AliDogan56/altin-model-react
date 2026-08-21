import { useEffect } from 'react';
import type { PanelFeature } from '../../content/types';
import { SITE_NAME } from '../../content/site';

const NAVBAR_OFFSET = 84;
const SETTLE_TICKS = 2;      // aynı yükseklik iki kez ölçülürse yerleşim durdu
const MAX_TRIES = 24;
const TICK_MS = 180;

/** /panel/<slug> ile gelindiyse: başlığı o özelliğe çevir, bölüme kaydır, kısa süre vurgula.
 *  Önce yerleşimin durulmasını bekler, sonra TEK yumuşak hareket yapar. Doğrudan smooth
 *  kaydırma denendiğinde sayfa yüklenirken yükseklik değiştiği için hedefi ıskalıyordu;
 *  anlık kaydırma ise sert görünüyordu. */
export const useFeatureFocus = (feature: PanelFeature | null) => {
  useEffect(() => {
    if (!feature) return;
    document.title = `${feature.seoTitle} | ${SITE_NAME}`;
    const set = (selector: string, value: string, attribute = 'content') => {
      const node = document.querySelector(selector);
      if (node) node.setAttribute(attribute, value);
    };
    set('meta[name="description"]', feature.summary);
    set('link[rel="canonical"]', `${window.location.origin}/panel/${feature.slug}`, 'href');

    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
    const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let timer: number, tries = 0, previousHeight = -1, settled = 0, started = false;

    /* Canlı bölümler (grafik, gösterge tablosu) hedefin altında sonradan büyüyor.
       Tek düzeltme yetmiyor: SPA gezinmesinde bölüm ekrandan kayıyordu. Birkaç kez
       sessizce hizalanır, sapma eşiğin altındaysa hiç dokunulmaz. */
    const corrections: number[] = [];
    const finish = (node: HTMLElement) => {
      node.classList.add('feature-focus');
      corrections.push(window.setTimeout(() => node.classList.remove('feature-focus'), 2400));
      let expected = -1;                       // en son bizim bıraktığımız konum
      (smooth ? [700, 1600, 3000] : [0, 900, 2200]).forEach(delay => {
        corrections.push(window.setTimeout(() => {
          // kullanıcı bu arada kendisi kaydırdıysa yerini geri alma
          if (expected >= 0 && Math.abs(window.scrollY - expected) > 40) return;
          const remaining = node.getBoundingClientRect().top - NAVBAR_OFFSET;
          if (Math.abs(remaining) > 24) window.scrollBy({ top: remaining, behavior: 'auto' });
          expected = window.scrollY;
        }, delay));
      });
    };

    const step = () => {
      const node = document.getElementById(feature.anchor);
      const height = document.body.scrollHeight;
      if (node && !started) {
        settled = height === previousHeight ? settled + 1 : 0;
        previousHeight = height;
        if (settled >= SETTLE_TICKS || tries >= 16) {
          started = true;
          window.scrollBy({ top: node.getBoundingClientRect().top - NAVBAR_OFFSET, behavior: smooth ? 'smooth' : 'auto' });
          finish(node);
          return;
        }
      }
      if (++tries < MAX_TRIES) timer = window.setTimeout(step, TICK_MS);
    };
    timer = window.setTimeout(step, 200);
    return () => { clearTimeout(timer); corrections.forEach(clearTimeout); };
  }, [feature]);
};
