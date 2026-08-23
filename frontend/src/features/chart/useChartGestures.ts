import { useEffect, useRef, type PointerEvent as ReactPointerEvent, type RefObject } from 'react';

const DRAG_THRESHOLD = 8;          // px — bu kadar kaymadan dokunuş "tıklama" sayılır
const WHEEL_STEP = 1.2;
/** Parmak çizim alanının bu kadar yakınına gelince grafik kendiliğinden kayar;
    yakınlaştırılmışken tek parmakla da görünür pencerenin dışına gidilebilsin. */
const EDGE_ZONE = 34;
const EDGE_SPEED = 0.45;           // kenara girilen piksel başına kaydırma

export type GestureConfig = {
  svgRef: RefObject<SVGSVGElement | null>;
  /** Bu kapsayıcının içine dokunmak sabitlemeyi bozmaz (gün gezinme çubuğu
      SVG'nin dışında duruyor ve düğmesine basmak ipucunu kapatıyordu). */
  keepRef?: RefObject<HTMLElement | null>;
  zoomBy: (factor: number) => void;
  panByPixels: (dx: number) => void;
  probeAt: (clientX: number) => void;
  clearProbe: () => void;
  pin: (value: boolean) => void;
  pinned: boolean;
};

/**
 * Grafik içi hareketler.
 *
 * **Dokunmada tek parmak seçim yapar, kaydırmaz.** Önceden tek parmak grafiği
 * kaydırıyordu ve bir günün değerini görmek için tam o güne dokunmak gerekiyordu;
 * 90 mumun 250 piksele sığdığı ekranda gün başına ~3 piksel düşüyor ve bu pratikte
 * imkânsızdı. Artık parmağı sürüklemek imleci gün gün gezdirir.
 * Kaydırma ve yakınlaştırma iki parmağa taşındı.
 *
 * Farede davranış değişmedi: sürükleme kaydırır, imleç zaten üzerine gelince okur.
 * Dikey sayfa kaydırma serbest kalsın diye CSS'te `touch-action: pan-y` durur.
 */
export const useChartGestures = (config: GestureConfig) => {
  const latest = useRef(config);
  latest.current = config;

  const pointers = useRef(new Map<number, number>());          // id -> clientX
  const spread = useRef(0);                                    // iki parmak arası son mesafe
  const midpoint = useRef(0);                                  // iki parmağın orta noktası
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
      const target = event.target as Node;
      if (latest.current.svgRef.current?.contains(target)) return;
      if (latest.current.keepRef?.current?.contains(target)) return;
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
      midpoint.current = (a + b) / 2;
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
      const centre = (a + b) / 2;
      if (spread.current > 10 && next > 10) zoomBy(next / spread.current);
      // Orta noktanın kayması kaydırmadır; tek parmak seçime ayrıldığı için
      // kaydırmanın tek yolu bu.
      if (midpoint.current) panByPixels(centre - midpoint.current);
      spread.current = next;
      midpoint.current = centre;
      return;
    }

    const active = drag.current;
    const pressed = active && (active.touch || event.buttons > 0);
    if (active && pressed) {
      if (!active.moved && Math.abs(event.clientX - active.startX) > DRAG_THRESHOLD) {
        active.moved = true;
        if (active.touch) pin(true);            // parmak gezdirirken kart açık kalsın
        else { clearProbe(); pin(false); }
      }
      if (active.moved) {
        if (active.touch) {
          probeAt(event.clientX);                   // parmak = imleci gezdir
          const box = latest.current.svgRef.current?.getBoundingClientRect();
          if (box) {
            const intoLeft = box.left + EDGE_ZONE - event.clientX;
            const intoRight = event.clientX - (box.right - EDGE_ZONE);
            if (intoLeft > 0) panByPixels(intoLeft * EDGE_SPEED);
            else if (intoRight > 0) panByPixels(-intoRight * EDGE_SPEED);
          }
        } else panByPixels(event.clientX - active.lastX);
        active.lastX = event.clientX;
        return;
      }
      if (active.touch) return;                 // eşiğe gelene kadar bekle
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
