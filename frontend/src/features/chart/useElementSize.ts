import { useLayoutEffect, useState, type RefObject } from 'react';

export type Size = { width: number; height: number };

const SAME = 0.5;   // yarım pikselden küçük fark yeni durum sayılmaz

/**
 * Ölçülen kutu, SVG'nin viewBox'ı olarak kullanılır: ölçek tam 1 olur, böylece
 * hem mektup kutusu (boş kenar) hem de yazı küçülmesi ortadan kalkar.
 *
 * Ölçüm üç kaynaktan beslenir; hiçbirine tek başına güvenilmez:
 *  - her render sonrası `useLayoutEffect` (yerleşimi değiştiren durum değişiklikleri,
 *    örneğin parametre panelinin açılıp kapanması) — boyamadan önce çalışır,
 *  - pencere yeniden boyutlandırma ve yön değişikliği,
 *  - varsa ResizeObserver (kabın kendi kendine büyümesi).
 * ResizeObserver'ın hiç tetiklenmediği ortamlar var; tek dayanak olsaydı grafik boş kalırdı.
 */
export const useElementSize = (ref: RefObject<Element | null>): Size => {
  const [size, setSize] = useState<Size>({ width: 0, height: 0 });

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;

    const measure = () => {
      const box = node.getBoundingClientRect();
      setSize(prev =>
        Math.abs(prev.width - box.width) < SAME && Math.abs(prev.height - box.height) < SAME
          ? prev
          : { width: box.width, height: box.height });
    };

    measure();
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure);
    observer?.observe(node);
    window.addEventListener('resize', measure);
    window.addEventListener('orientationchange', measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', measure);
      window.removeEventListener('orientationchange', measure);
    };
  });

  return size;
};
