import { useEffect, useRef, type PointerEvent as ReactPointerEvent, type RefObject } from 'react';

const DRAG_THRESHOLD = 8;          // px — bu kadar kaymadan dokunuş "tıklama" sayılır
const WHEEL_STEP = 1.2;

export type GestureConfig = {
  svgRef: RefObject<SVGSVGElement | null>;
  zoomBy: (factor: number) => void;
  panByPixels: (dx: number) => void;
  probeAt: (clientX: number) => void;
  clearProbe: () => void;
  pin: (value: boolean) => void;
  pinned: boolean;
};

/**
 * Grafik içi hareketler: fare sürükleyerek kaydırma, iki parmakla yakınlaştırma,
 * dokun-sabitle imleç ve Ctrl gerektirmeyen tekerlek zoom'u.
 * Dikey sayfa kaydırma serbest kalsın diye CSS'te `touch-action: pan-y` durur;
 * yatay hareket ve iki parmak bize gelir.
 */
export const useChartGestures = (config: GestureConfig) => {
  const latest = useRef(config);
  latest.current = config;

  const pointers = useRef(new Map<number, number>());          // id -> clientX
  const spread = useRef(0);                                    // iki parmak arası son mesafe
  const drag = useRef<{ startX: number; lastX: number; moved: boolean; touch: boolean } | null>(null);

  // React tekerlek dinleyicisini passive bağlıyor; preventDefault için kendimiz kuruyoruz.
  useEffect(() => {
    const node = latest.current.svgRef.current;
    if (!node) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      latest.current.zoomBy(event.deltaY < 0 ? WHEEL_STEP : 1 / WHEEL_STEP);
    };
    node.addEventListener('wheel', onWheel, { passive: false });
    return () => node.removeEventListener('wheel', onWheel);
  }, []);

  // Sabitlenmiş ipucu, grafiğin dışına dokununca kapanır.
  useEffect(() => {
    if (!config.pinned) return;
    const onOutside = (event: Event) => {
      if (latest.current.svgRef.current?.contains(event.target as Node)) return;
      latest.current.clearProbe();
      latest.current.pin(false);
    };
    document.addEventListener('pointerdown', onOutside);
    return () => document.removeEventListener('pointerdown', onOutside);
  }, [config.pinned]);

  const onPointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
    const touch = event.pointerType !== 'mouse';
    pointers.current.set(event.pointerId, event.clientX);
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      spread.current = Math.abs(a - b);
      drag.current = null;
      return;
    }
    // yakalama başarısız olabilir (sentetik olay, iptal edilmiş işaretçi); hareket buna bağlı değil
    if (touch) { try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* yoksay */ } }
    drag.current = { startX: event.clientX, lastX: event.clientX, moved: false, touch };
  };

  const onPointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    const { zoomBy, panByPixels, probeAt, clearProbe, pin } = latest.current;

    if (pointers.current.has(event.pointerId)) pointers.current.set(event.pointerId, event.clientX);
    if (pointers.current.size >= 2) {
      const [a, b] = [...pointers.current.values()];
      const next = Math.abs(a - b);
      if (spread.current > 10 && next > 10) zoomBy(next / spread.current);
      spread.current = next;
      return;
    }

    const active = drag.current;
    const pressed = active && (active.touch || event.buttons > 0);
    if (active && pressed) {
      if (!active.moved && Math.abs(event.clientX - active.startX) > DRAG_THRESHOLD) {
        active.moved = true;
        clearProbe();
        pin(false);
      }
      if (active.moved) {
        panByPixels(event.clientX - active.lastX);
        active.lastX = event.clientX;
        return;
      }
      if (active.touch) return;                 // dokunuşta sürüklenene kadar imleci oynatma
    }
    if (event.pointerType === 'mouse') probeAt(event.clientX);
  };

  const endPointer = (event: ReactPointerEvent<SVGSVGElement>) => {
    const active = drag.current;
    pointers.current.delete(event.pointerId);
    if (pointers.current.size < 2) spread.current = 0;
    drag.current = null;
    if (active?.touch && !active.moved) {       // kısa dokunuş: imleci sabitle
      latest.current.probeAt(event.clientX);
      latest.current.pin(true);
    }
  };

  const onPointerLeave = () => {
    if (latest.current.pinned) return;
    latest.current.clearProbe();
  };

  return { onPointerDown, onPointerMove, onPointerUp: endPointer, onPointerCancel: endPointer, onPointerLeave };
};
