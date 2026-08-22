import type { ParameterGroup } from './types';

export const GROUPS: ParameterGroup[] = [
  ['Fiyat ve teknik', [['price', 'Ons fiyatı', 'USD'], ['gold_return_1d', '1 günlük momentum', '%'],
    ['gold_return_5d', '5 günlük momentum', '%'], ['gold_return_20d', '20 günlük momentum', '%'],
    ['gold_ma_ratio_50d', '50 günlük ortalamadan sapma', '%'], ['gold_rsi14_centered', 'Merkezlenmiş RSI', ''],
    ['gold_atr14_pct', '14 günlük fiyat aralığı (ATR)', '%'],
    ['gold_volatility_20d', '20 günlük oynaklık', '%'], ['gold_drawdown_60d', '60 günlük zirveden düşüş', '%']]],
  ['Faiz ve dolar', [['real_yield_change_5d', 'Reel faiz 5 günlük değişim', 'puan'],
    ['real_yield_change_20d', 'Reel faiz 20 günlük değişim', 'puan'],
    ['dollar_return_5d', 'Dolar endeksi 5 günlük getiri', '%'],
    ['dollar_return_20d', 'Dolar endeksi 20 günlük getiri', '%'],
    ['breakeven_change_20d', 'Breakeven 20 günlük değişim', 'puan'],
    ['yield_curve_10y_2y', 'ABD 10Y–2Y eğrisi', 'puan']]],
  ['Risk ve emtia', [['vix_level', 'VIX', ''], ['vix_change_5d', 'VIX 5 günlük değişim', 'puan'],
    ['oil_return_5d', 'Petrol 5 günlük getiri', '%'], ['oil_return_20d', 'Petrol 20 günlük getiri', '%']]],
  ['Makroekonomi', [['core_cpi_yoy', 'Çekirdek TÜFE yıllık', '%']]],
];

export const PARAMETER_IDS = GROUPS.flatMap(([, items]) => items).map(([id]) => id);

/** Katkı kartı için sade dil: her girdinin günlük karşılığı ve neden önemli olduğu.
 *  Teknik adlar ("breakeven", "ATR", "z-skor") hiçbir şey bilmeyen okuyucuya
 *  bir şey anlatmıyordu; kart artık bu sözlükten konuşuyor. 19 girdinin tamamı
 *  burada: eskiden yalnız 14'ü listeleniyordu ve en büyük etki bile gizli kalıyordu. */
export type ImpactLabel = { label: string; hint: string };

export const IMPACT_LABELS: Record<string, ImpactLabel> = {
  gold_drawdown_60d: { label: 'Zirveden ne kadar uzakta',
    hint: 'Altın son 2 ayın en yüksek seviyesinden ne kadar geri çekilmiş. Çok geri çekilmişse toparlanma payı var demektir.' },
  gold_return_5d: { label: 'Son 5 gündeki hareket',
    hint: 'Kısa sürede çok hızlı yükselen fiyat, genelde bir süre soluklanır.' },
  gold_return_1d: { label: 'Dünden bugüne hareket', hint: 'Son bir günün değişimi.' },
  gold_return_20d: { label: 'Son 1 aydaki hareket', hint: 'Orta vadeli yön: altın son bir ayda hangi yöne gidiyor.' },
  gold_ma_ratio_50d: { label: 'Ortalama fiyattan uzaklık',
    hint: 'Fiyat son 50 günün ortalamasının ne kadar üstünde. Arayı çok açtıysa geri çekilme olasılığı artar.' },
  gold_rsi14_centered: { label: 'Alıcı-satıcı dengesi',
    hint: 'Alıcıların satıcılara üstünlüğü. Çok yüksekse "herkes almış, alacak kimse kalmamış" anlamına gelebilir.' },
  gold_atr14_pct: { label: 'Günlük fiyat oynaması',
    hint: 'Fiyatın gün içinde ortalama ne kadar savrulduğu. Yükselmesi piyasanın gerginleştiğini gösterir.' },
  gold_volatility_20d: { label: 'Son 1 ayın dalgalanması',
    hint: 'Fiyatın bir aydır ne kadar oynak olduğu.' },
  real_yield_change_5d: { label: 'Faizin son 5 günü',
    hint: 'Enflasyondan arındırılmış ABD faizi. Yükselmesi altını tutmayı pahalı hâle getirir.' },
  real_yield_change_20d: { label: 'Faizin son 1 ayı',
    hint: 'Enflasyondan arındırılmış ABD faizinin bir aylık yönü. Düşerse altın cazipleşir.' },
  dollar_return_5d: { label: 'Doların son 5 günü',
    hint: 'Altın dolarla fiyatlanır; dolar güçlenince altın diğer para birimleri için pahalılaşır.' },
  dollar_return_20d: { label: 'Doların son 1 ayı',
    hint: 'Doların bir aylık gücü. Güçlü dolar genelde altını baskılar.' },
  breakeven_change_20d: { label: 'Beklenen enflasyon',
    hint: 'Piyasanın gelecek için fiyatladığı enflasyon. Yükselmesi altına ilgiyi artırır.' },
  core_cpi_yoy: { label: 'ABD enflasyonu',
    hint: 'Yıllık çekirdek enflasyon. Yüksek enflasyon altını değer koruma aracı olarak öne çıkarır.' },
  yield_curve_10y_2y: { label: 'Uzun-kısa faiz farkı',
    hint: 'Uzun vadeli faizin kısa vadeliden farkı. Daralması ekonomide yavaşlama sinyali sayılır.' },
  vix_level: { label: 'Piyasa korkusu',
    hint: 'Borsadaki tedirginlik ölçüsü (VIX). Korku arttıkça güvenli liman talebi artar.' },
  vix_change_5d: { label: 'Korkunun son 5 günü', hint: 'Tedirginliğin artıp azaldığı yön.' },
  oil_return_5d: { label: 'Petrolün son 5 günü', hint: 'Petrol pahalanınca enflasyon beklentisi de yükselir.' },
  oil_return_20d: { label: 'Petrolün son 1 ayı', hint: 'Petrolün bir aylık yönü.' },
};
