import type { Direction, MomentumTrend } from '../services/api/momentum';
import type { Labeled, StrengthTone } from './technical';

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

/** Kırılım etiketi; sunucu sözlüğü (`breakout.py`, `levels.py` ile aynı). */
export type BreakLabel = 'STRONG' | 'MODERATE' | 'WEAK';

type BreakEntry = { label: string; tone: StrengthTone; note: string };

const BREAK_ENTRIES: Record<BreakLabel, BreakEntry> = {
  STRONG: { label: 'GÜÇLÜ', tone: 'strong',
    note: 'bu mesafeyi kapatmaya yetiyor ve arkasında momentum var' },
  MODERATE: { label: 'ORTA', tone: 'medium',
    note: 'seviye erişilebilir ama kırmak için gereken güç tam oluşmamış' },
  WEAK: { label: 'ZAYIF', tone: 'weak',
    note: 'mevcut hareket bu seviyeyi zorlamaya yetmiyor' },
};

/**
 * Yalnız sunucunun `breakout` bloğu okunur. Seans bloğunun eski `breakout`
 * alt nesnesi hâlâ `MEDIUM` diyor ama `parseMomentum` onu okumaz; bu yüzden
 * burada alias yok.
 */
export const BREAK: Record<BreakLabel, BreakEntry> = BREAK_ENTRIES;

/* --- günlük momentum (momentum_daily.py) ------------------------------------ */

export type DailyDirection = 'UP' | 'DOWN' | 'NEUTRAL';
export type DailyStrength = 'STRONG' | 'MODERATE' | 'WEAK';
export type DailyTrend = 'STRENGTHENING' | 'WEAKENING' | 'STABLE';
export type DailyNote = 'CONFLICTING';

/**
 * Günlük mumlardan bileşik momentum: "son haftaların hareketi ne kadar tek
 * yönlü ve kararlı?" Gün içi bloktan ayrı bir sorudur; sözlükleri de ayrı.
 * `note.CONFLICTING`: NEUTRAL ama uyum düşük — piyasa durgun değil,
 * göstergeler çelişiyor.
 */
export const MOMENTUM_DAILY: {
  direction: Record<DailyDirection, Labeled>;
  strength: Record<DailyStrength, Labeled<StrengthTone>>;
  trend: Record<DailyTrend, string>;
  note: Record<DailyNote, string>;
} = {
  direction: {
    UP: { label: 'Yukarı yönlü', tone: 'up' },
    DOWN: { label: 'Aşağı yönlü', tone: 'down' },
    NEUTRAL: { label: 'Yönsüz', tone: 'flat' },
  },
  strength: {
    STRONG: { label: 'Güçlü', tone: 'strong' },
    MODERATE: { label: 'Orta', tone: 'medium' },
    WEAK: { label: 'Zayıf', tone: 'weak' },
  },
  trend: {
    STRENGTHENING: 'güçleniyor',
    WEAKENING: 'zayıflıyor',
    STABLE: 'sabit',
  },
  note: {
    CONFLICTING: 'Bileşenler çelişiyor',
  },
};
