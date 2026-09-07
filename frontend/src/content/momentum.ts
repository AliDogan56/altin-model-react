import type { BreakStrength, Direction, MomentumTrend } from '../services/api/momentum';

/**
 * Momentum bölümünün ve grafik altındaki özet kartın **ortak** sözlüğü.
 * İki yerde ayrı yazılırsa aynı durum iki farklı kelimeyle anlatılır.
 */
export const DIRECTION: Record<Direction, { label: string; tone: string; note: string }> = {
  UP: { label: 'Yukarı', tone: 'up', note: 'fiyat yükseliş yönünde ilerliyor' },
  DOWN: { label: 'Aşağı', tone: 'down', note: 'fiyat düşüş yönünde ilerliyor' },
  NEUTRAL: { label: 'Yönsüz', tone: 'flat',
    note: 'hareket, seansın kendi dalgalanmasından ayırt edilemiyor' },
};

export const TREND: Record<MomentumTrend, string> = {
  STRENGTHENING: 'güçleniyor',
  WEAKENING: 'zayıflıyor',
  STABLE: 'hızını koruyor',
};

export const BREAK: Record<BreakStrength, { label: string; tone: string; note: string }> = {
  STRONG: { label: 'GÜÇLÜ', tone: 'strong',
    note: 'bu mesafeyi kapatmaya yetiyor ve arkasında momentum var' },
  MEDIUM: { label: 'ORTA', tone: 'medium',
    note: 'seviye erişilebilir ama kırmak için gereken güç tam oluşmamış' },
  WEAK: { label: 'ZAYIF', tone: 'weak',
    note: 'mevcut hareket bu seviyeyi zorlamaya yetmiyor' },
};

/** Özet kartta yer dar; uzun karşılıkları momentum bölümünde duruyor. */
export const BREAK_SHORT: Record<BreakStrength, string> = {
  STRONG: 'güçlü', MEDIUM: 'orta', WEAK: 'zayıf',
};
