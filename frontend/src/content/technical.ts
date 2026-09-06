/**
 * Teknik analiz DTO'sunun (`/v1/market/xau/technical`) ortak sözlüğü.
 *
 * Sunucu yalnız **enum anahtarı** döner; Türkçe metin ve renk tonu tek yerde,
 * burada üretilir. Anahtar kümeleri `backend/market-service/app/services/
 * technical/` altındaki sabitlerin birebir aynasıdır (levels.py, pivots.py,
 * breakout.py, assemble.py, reference.py). `Record<…>` tipleri sayesinde
 * sunucuya yeni bir değer eklenip buraya yazılmazsa derleme değil,
 * `content.test.ts` (fixture taraması) yakalar.
 */

/** Renk tonu = CSS sınıf kancası; `.indicator-state.up` gibi. */
export type Tone = 'up' | 'down' | 'flat' | 'warn';
/** Güç ölçeği tonu; `.momentum-break.strong` gibi. */
export type StrengthTone = 'strong' | 'medium' | 'weak';

export type Labeled<T extends string = Tone> = { label: string; tone: T };

/* --- durumlar ----------------------------------------------------------- */

/** Blok (`status.*`), yan (`levels.side_status`, `breakout.up/down`) ve
 *  referans durumlarının birleşimi. */
export type BlockStatus =
  | 'OK'
  | 'NO_DATA'
  | 'INSUFFICIENT_DATA'
  | 'FLAT_MARKET'
  | 'INTRADAY_UNAVAILABLE'
  | 'INTRADAY_STALE'
  | 'SESSION_TOO_SHORT'
  | 'FLAT_SESSION'
  | 'PERIOD_INCOMPLETE_FALLBACK'
  | 'PERIOD_UNAVAILABLE'
  | 'NO_VALID_SUPPORT'
  | 'NO_VALID_RESISTANCE'
  | 'NO_TARGET_ABOVE'
  | 'NO_TARGET_BELOW';

/** Boş durum cümlesi; `OK` için mesaj yok (`null`). */
export const STATUS_TEXT: Record<BlockStatus, string | null> = {
  OK: null,
  NO_DATA: 'Günlük fiyat verisi alınamadı',
  INSUFFICIENT_DATA: 'Hesap için yeterli günlük mum yok',
  FLAT_MARKET: 'Seri düz; oynaklık sıfır olduğu için hesap yapılamadı',
  INTRADAY_UNAVAILABLE: 'Gün içi veri alınamadı; günlük kapanış kullanıldı',
  INTRADAY_STALE: 'Gün içi veri günlük seriden eski; günlük kapanış kullanıldı',
  SESSION_TOO_SHORT: 'Seans yeni açıldı; yeterli 5 dakikalık mum yok',
  FLAT_SESSION: 'Seans düz; mumlar arasında ölçülebilir hareket yok',
  PERIOD_INCOMPLETE_FALLBACK: 'Dönemin kapanış mumu henüz gelmedi; bir önceki dönem gösteriliyor',
  PERIOD_UNAVAILABLE: 'Bu dönem için tamamlanmış bir mum yok',
  NO_VALID_SUPPORT: 'Altta yeterince test edilmiş bir destek yok',
  NO_VALID_RESISTANCE: 'Üstte yeterince test edilmiş bir direnç yok',
  NO_TARGET_ABOVE: 'Üstte hedef alınacak bir seviye yok',
  NO_TARGET_BELOW: 'Altta hedef alınacak bir seviye yok',
};

/* --- notlar --------------------------------------------------------------- */

export type TechnicalNote =
  | 'NOT_A_PROBABILITY'
  | 'UNTESTED_LEVEL'
  | 'NO_EXPECTED_MOVE'
  | 'LIVE_QUOTE_NOT_USED';

export const NOTE_TEXT: Record<TechnicalNote, string> = {
  NOT_A_PROBABILITY: 'Bu gösterge bir kırılım olasılığı yüzdesi değildir',
  UNTESTED_LEVEL: 'Hedef, hiç test edilmemiş bir pivot çizgisi; bölge gücü bilinmiyor',
  NO_EXPECTED_MOVE: 'Beklenen hareket sıfır; kırılım gücü ölçülemedi',
  LIVE_QUOTE_NOT_USED: 'Canlı kotasyon hesaba girmez; referans vadeli altın kapanışıdır',
};

/* --- referans çerçevesi --------------------------------------------------- */

export type ReferenceFrame = 'intraday_close' | 'daily_close';

export const FRAME: Record<ReferenceFrame, string> = {
  intraday_close: 'Vadeli altın · 5 dk kapanış',
  daily_close: 'Vadeli altın · günlük kapanış',
};

export type ExpectedMoveFrame = 'session_remaining' | 'next_daily_bar';

/** Beklenen hareketin ufku; cümle içinde kullanılır ("… seansın kalanında"). */
export const EXPECTED_MOVE_FRAME: Record<ExpectedMoveFrame, string> = {
  session_remaining: 'seansın kalanında',
  next_daily_bar: 'sonraki günlük mumda',
};

export type MarketState = 'OPEN' | 'CLOSED';

export const MARKET_STATE: Record<MarketState, Labeled> = {
  OPEN: { label: 'Piyasa açık', tone: 'up' },
  CLOSED: { label: 'Piyasa kapalı', tone: 'flat' },
};

/* --- güç ölçeği (bölge etiketi ve kırılım etiketi aynı sözlük) ------------ */

export type Strength3 = 'STRONG' | 'MODERATE' | 'WEAK';

export const STRENGTH3: Record<Strength3, Labeled<StrengthTone>> = {
  STRONG: { label: 'Güçlü', tone: 'strong' },
  MODERATE: { label: 'Orta', tone: 'medium' },
  WEAK: { label: 'Zayıf', tone: 'weak' },
};

/**
 * Bölge etiketi bir **test yoğunluğu** sözüdür, "güçlü seviye" iddiası değil:
 * doğrulama raporu etiket sırasının tutma oranını sıralamadığını ölçtü
 * (VALIDATION.md, karar 1). Renk tonu STRENGTH3'ten, kelime buradan; merdiven
 * ve momentum kartı aynı sözlüğü okur ki iki yerde iki ayrı ifade çıkmasın.
 */
export const TEST_INTENSITY: Record<Strength3, string> = {
  STRONG: 'çok test edildi',
  MODERATE: 'orta düzeyde test edildi',
  WEAK: 'az test edildi',
};

/** Teknik paket hiç gelmediğinde (ağ/şema) her kartın yazdığı ortak cümle. */
export const SERVICE_UNREACHABLE = 'Teknik analiz servisine ulaşılamadı';

/* --- seviyeler ------------------------------------------------------------ */

export type LevelKind = 'SUPPORT' | 'RESISTANCE';

export const LEVEL_KIND: Record<LevelKind, Labeled> = {
  SUPPORT: { label: 'Destek', tone: 'up' },
  RESISTANCE: { label: 'Direnç', tone: 'down' },
};

export type LevelRole = 'NEAREST_UP' | 'NEAREST_DOWN' | 'TESTING';

export const LEVEL_ROLE: Record<LevelRole, Labeled> = {
  NEAREST_UP: { label: 'En yakın direnç', tone: 'down' },
  NEAREST_DOWN: { label: 'En yakın destek', tone: 'up' },
  TESTING: { label: 'Test ediliyor', tone: 'warn' },
};

export type PositionVsPivot = 'ABOVE' | 'BELOW' | 'AT';

export const POSITION_VS_PIVOT: Record<PositionVsPivot, Labeled> = {
  ABOVE: { label: 'Pivotun üstünde', tone: 'up' },
  BELOW: { label: 'Pivotun altında', tone: 'down' },
  AT: { label: 'Pivot seviyesinde', tone: 'warn' },
};

export type Outside = 'ABOVE_ALL' | 'BELOW_ALL';

export const OUTSIDE: Record<Outside, string> = {
  ABOVE_ALL: 'Fiyat merdivendeki tüm seviyelerin üstünde',
  BELOW_ALL: 'Fiyat merdivendeki tüm seviyelerin altında',
};

export type BreakoutSide = 'up' | 'down';

/** `breakout.headline`: seans yönünün öne çıkardığı yan. */
export const BREAKOUT_SIDE: Record<BreakoutSide, string> = {
  up: 'Yukarı: ilk direnç',
  down: 'Aşağı: ilk destek',
};

/** Kırılım kartının başlığı; iki yan her zaman çizilir (karar 2). */
export const BREAKOUT_SIDE_TITLE: Record<BreakoutSide, string> = {
  up: 'Yukarı kırılım gücü',
  down: 'Aşağı kırılım gücü',
};

export type SourceType = 'swing' | 'pivot' | 'range_extreme' | 'round';

export const SOURCE_TYPE: Record<SourceType, string> = {
  swing: 'Salınım',
  pivot: 'Pivot',
  range_extreme: 'Aralık ucu',
  round: 'Yuvarlak seviye',
};

const PIVOT_PREFIX: Record<string, string> = { W: 'Haftalık', M: 'Aylık', D: 'Günlük' };

/**
 * Bölge kaynağı etiketini Türkçeleştirir. Etiketler sunucuda üç kalıptan
 * gelir: `SWING_HIGH/LOW`, `HIGH_n/LOW_n` (n günlük uç değer), `ROUND` ve
 * `W_R1 / M_P / D_P` (dönem öneki + pivot adı). Tanınmayan etiket olduğu gibi döner.
 */
export const sourceLabel = (label: string): string => {
  if (label === 'SWING_HIGH') return 'salınım zirvesi';
  if (label === 'SWING_LOW') return 'salınım dibi';
  if (label === 'ROUND') return 'yuvarlak seviye';
  const range = /^(HIGH|LOW)_(\d+)$/.exec(label);
  if (range) return `${range[2]} günlük ${range[1] === 'HIGH' ? 'zirve' : 'dip'}`;
  const pivot = /^([WMD])_([RS]\d|P)$/.exec(label);
  if (pivot) return `${PIVOT_PREFIX[pivot[1]]} ${pivot[2]}`;
  return label;
};

/* --- pivotlar ------------------------------------------------------------- */

export type PivotMethod = 'CLASSIC' | 'FIBONACCI' | 'CAMARILLA';
export type PivotPeriod = 'DAILY' | 'WEEKLY' | 'MONTHLY';

export const PIVOT_METHOD: Record<PivotMethod, string> = {
  CLASSIC: 'Klasik',
  FIBONACCI: 'Fibonacci',
  CAMARILLA: 'Camarilla',
};

export const PIVOT_PERIOD: Record<PivotPeriod, string> = {
  DAILY: 'Günlük',
  WEEKLY: 'Haftalık',
  MONTHLY: 'Aylık',
};

export type Completion = 'LAST_BAR_PRESENT' | 'SUCCEEDED_BY_LATER_BAR' | 'GRACE_ELAPSED' | 'NONE';

/** Dönemin neden "bitmiş" sayıldığı; bayatlık buradan okunur. */
export const COMPLETION: Record<Completion, string> = {
  LAST_BAR_PRESENT: 'Dönemin kapanış mumu geldi',
  SUCCEEDED_BY_LATER_BAR: 'Sonraki dönemden mum geldi; dönem kapanmış sayıldı',
  GRACE_ELAPSED: 'Kapanış mumu gelmedi; bekleme süresi dolduğu için dönem kapanmış sayıldı',
  NONE: 'Tamamlanmış dönem seçilemedi',
};
