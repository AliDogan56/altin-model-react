import type { BreakStrength } from '../../services/api/momentum';

/**
 * Panelin gösterdiği seviyenin kırılma gücü.
 *
 * Momentum servisi kırılım gücünü **kendi** merdiveni için hesaplar (günlük
 * pivotlar + haftalık + salınım). Grafiğin altındaki kartlar ise pivot kartının
 * seçtiği merdiveni gösterir. İki liste farklı seviyeler içerdiği için kart
 * komşusundan başka bir sayıdan bahsediyordu; kullanıcı bunu bildirdi.
 *
 * Hesap **oransal** yapılır. Momentum gün içi akıştan (Yahoo `GC=F`, vadeli),
 * kartlar Harem'den (spot) besleniyor ve ikisi arasında ~%1 seviye farkı var.
 * Dolar cinsinden karşılaştırmak bu farkı mesafeye karıştırır; oranda ise fark
 * sadeleşir çünkü beklenen hareket de fiyatla orantılıdır.
 */
export type BreakPotential = {
  /** Beklenen hareket ÷ uzaklık; 1 "tam ulaşır" demektir, üstü doyurulur. */
  reach: number;
  score: number;
  strength: BreakStrength;
};

export const breakPotential = (
  /** Kartın gösterdiği seviye ve o kartın kendi fiyatı — **aynı** çerçeveden. */
  level: number, price: number,
  /** Momentum çerçevesinden: seansın kalanında beklenen hareket, oran olarak. */
  expectedMovePct: number,
  /** Momentum gücü, 0-100. */
  strength: number,
): BreakPotential | null => {
  if (!Number.isFinite(level) || !Number.isFinite(price) || price <= 0) return null;
  if (!Number.isFinite(expectedMovePct) || expectedMovePct <= 0) return null;
  if (!Number.isFinite(strength)) return null;

  const distance = Math.abs(level / price - 1);
  // Fiyat seviyenin tam üstündeyse "kırma" sorusu anlamsız; uzaklık sıfır.
  if (distance <= 0) return null;

  // Ulaşma 1'de doyurulur: seviyenin dibinde olmak onu kırmakla aynı şey değil.
  const reach = expectedMovePct / distance;
  const score = Math.sqrt(Math.min(1, reach) * Math.max(0, Math.min(100, strength)) / 100);
  const label: BreakStrength = score >= 2 / 3 ? 'STRONG' : score >= 1 / 3 ? 'MEDIUM' : 'WEAK';
  return { reach, score, strength: label };
};

/** Panelin pivot merdiveninden bir basamak (`domain/pivots.ts` → `LadderItem`). */
export type PanelLevel = { name: string; value: number; above: boolean };

export type MomentumTarget = {
  side: 'support' | 'resistance';
  level: PanelLevel;
} | null;

/**
 * Momentumun hedefi **yönünden** çıkar: yukarı yönlüyse üstteki ilk direnç,
 * aşağı yönlüyse alttaki ilk destek. `NEUTRAL` iken hedef yoktur — yön
 * belirsizken "şu seviyeyi kırar" demek uydurma olur.
 */
export const momentumTarget = (
  direction: 'UP' | 'DOWN' | 'NEUTRAL',
  support: PanelLevel | null | undefined,
  resistance: PanelLevel | null | undefined,
): MomentumTarget => {
  if (direction === 'UP') return resistance ? { side: 'resistance', level: resistance } : null;
  if (direction === 'DOWN') return support ? { side: 'support', level: support } : null;
  return null;
};

/**
 * Fiyatın gürültü kadar yakınında duran seviye. Böyle bir seviye "kırılacak"
 * değil **test ediliyor** demektir; hedefi değiştirmez, ayrı bir not olarak
 * yazılır. Marj servisteki `CLUSTER_BARS` ile aynı: mum başına oynaklığın
 * 4 mumluk karekök ölçeği.
 */
export const TOUCH_BARS = 4;

export const touchingLevel = (
  items: readonly PanelLevel[], price: number, barSigmaPct: number,
): PanelLevel | null => {
  if (!Number.isFinite(price) || price <= 0) return null;
  if (!Number.isFinite(barSigmaPct) || barSigmaPct <= 0) return null;
  const margin = (barSigmaPct / 100) * Math.sqrt(TOUCH_BARS);
  let best: PanelLevel | null = null;
  let bestGap = Infinity;
  for (const item of items) {
    const gap = Math.abs(item.value / price - 1);
    if (gap <= margin && gap < bestGap) { best = item; bestGap = gap; }
  }
  return best;
};
