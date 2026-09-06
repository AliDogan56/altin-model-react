# Teknik analiz paketi — çevrimdışı doğrulama

<!-- ta:header:start -->
| Alan | Değer |
|---|---|
| Tarih | 2026-09-06 |
| Veri seti | `tests/fixtures/xau_daily_20260906.json` — 1257 tamamlanmış günlük mum, 2021-09-07 → 2026-09-04 (GC=F türevi) |
| Veri seti sha256 | `8f3740da01ab1dfe1e0c25b1cfa0348857bc35c2f9b079485517b0126adf7b0f` |
| config_hash | `8cc57c8db10f` (`TechnicalConfig.config_hash()`, ortam değişkeni ezmesi yok) |
| Paket sürümü | `technical-v1` |
| Python | 3.14.6, numpy yok |
<!-- ta:header:end -->

Bu belge `backend/market-service/scripts/ta_*.py` betiklerinin çıktısıdır. Betikler yalnız `tests/fixtures/` altındaki 2026-09-06 fixture'larını okur; ağa çıkmaz, sunucu açmaz, paket parametresine dokunmaz. Her bölüm kendi betiğiyle yeniden üretilir; "Karar önerileri" elle yazılır ve betikler onu korur. Sayılar ölçümdür, öneri değildir — bir eşiği dondurma kararı insanındır.

<!-- ta:section:eski-yeni:start -->
## Eski → yeni
Taban çizgisi 2026-09-06, `now` = 2026-09-06T10:02:05+00:00 (testlerle aynı). Blok durumu 8/8 OK; referans 4476.6 (`intraday_close`), ATR14 86.66 $, σ20 0.0145.

### (a) Referans fiyat: eski Harem spot → yeni GC=F gün içi kapanış
| Taraf | Fiyat | Merdiven | En yakın üst | En yakın alt | Test ediliyor | Çerçeve |
|---|---|---|---|---|---|---|
| Eski: Harem spot satış | 4431.6 | haftalık klasik | P | S1 | — | spot (Harem), arayüz kuralı marj 0 |
| Eski: Harem spot satış | 4431.6 | haftalık fib | P | S1 | — | spot (Harem), arayüz kuralı marj 0 |
| Eski: Harem + dokunma marjı | 4431.6 | haftalık klasik | R1 | S1 | P | spot, `touchingLevel` marjı %0.2722 = 12.1 $ |
| Eski: Harem + dokunma marjı | 4431.6 | haftalık fib | R1 | S1 | P | spot, `touchingLevel` marjı %0.2722 = 12.1 $ |
| Yeni: gün içi son kapanış | 4476.6 | haftalık klasik | R1 | P | — | `intraday_close` GC=F, marj 0.25·ATR = 21.7 $ |
| Yeni: gün içi son kapanış | 4476.6 | haftalık fib | R1 | P | — | `intraday_close` GC=F, marj 0.25·ATR = 21.7 $ |

İki merdiven de aynı haftalık mumdan (`2026-08-31`, H 4537.8 / L 4292.2 / C 4476.6) çıkıyor; seviyeler birebir aynı. Değişen yalnız **referans fiyat**: Harem spot GC=F kapanışının %1.005 altında (4431.6 ↔ 4476.6) ve haftalık P = 4435.53 tam bu iki fiyatın arasına düşüyor. Spot çerçevesinde P 3.9 $ yukarıda ("en yakın üst", hatta eski dokunma marjıyla "dokunulan"), kapanış çerçevesinde 41.1 $ aşağıda ("en yakın alt"). Yeni paket Harem'i hiç okumaz (`reference.note = LIVE_QUOTE_NOT_USED`): merdiven, bölgeler, ATR ve seans beklenen hareketi tek çerçevede (GC=F) kalır; canlı spot yalnız başlıkta kotasyon olarak gösterilir.

### (b) Pivotlar: parite ve başlık merdiveni
Eski arayüzle parite: **224/224** seviye değeri (canlı 2 çerçeve × 4 varyant × 7, tolerans 1e-3 — fixture 4 ondalık; tarihsel 6 gün × 4 varyant × 7, tolerans 1e-6) ve **96/96** hedef alanı (`nearestUp` / `nearestDown` / `insertAt`) eşleşti. Aynı denetim `tests/test_technical_pivots.py` içinde (testin kendi 28 sabitiyle 252/252) sürekli koşar; burada yalnız fixture'daki sayı tekrarlanır.

Başlık merdiveni, referans 4476.6 $, marj 21.7 $ (0.25·ATR14). Eski varsayılan **haftalık Fibonacci** idi; yeni başlık **haftalık klasik**, Fibonacci istek parametresiyle seçilebilir (`?pivot_method=`). Dönem `2026-08-31`, durum `OK` / `LAST_BAR_PRESENT`.

| Basamak | Klasik | Δ% | Rol | Fibonacci | Δ% | Rol |
|---|---|---|---|---|---|---|
| R3 | 4824.47 | %+7.77 | — | 4681.13 | %+4.57 | — |
| R2 | 4681.13 | %+4.57 | — | 4587.31 | %+2.47 | — |
| R1 | 4578.87 | %+2.28 | NEAREST_UP | 4529.35 | %+1.18 | NEAREST_UP |
| P | 4435.53 | %-0.92 | NEAREST_DOWN | 4435.53 | %-0.92 | NEAREST_DOWN |
| S1 | 4333.27 | %-3.20 | — | 4341.71 | %-3.01 | — |
| S2 | 4189.93 | %-6.40 | — | 4283.75 | %-4.31 | — |
| S3 | 4087.67 | %-8.69 | — | 4189.93 | %-6.40 | — |

İkisinde de en yakın hedefler R1 (üst) ve P (alt); klasik R1 %2.28, Fibonacci R1 %1.18 uzakta — Fibonacci R1 = P + 0.382·aralık olduğu için klasik R1'den (2P − L) her zaman P'ye daha yakındır. Fibonacci R3 klasik R2 ile, S3 klasik S2 ile aynı sayıdır (cebirsel özdeşlik, testte sabit).

### (c) Göstergeler: eski tarayıcı tanımı → Wilder standardı
Aynı 1257 mum, son kapanış 4476.6. Eski değerler arayüzün gösterdiği yuvarlanmış metinler (`indicators_old_fe_20260906.json`), yeni değerler `latest_indicators` çıktısı.

| Gösterge | Eski | Yeni | Δ | Tanım farkı | Eski durum | Yeni durum |
|---|---|---|---|---|---|---|
| RSI (14) | 53.7 | 55.7 | +2.0 | Cutler (14 kazanç/kayıp basit ortalaması) → **Wilder** (α = 1/14, SMA tohum); düz seride eski 0, yeni 50 | Nötr bölge | NEUTRAL |
| Stochastic %K (14) | 48.7 | 48.7 | -0.0 | aynı tanım (hızlı %K, HH−LL = 0 → 50) | Nötr bölge | NEUTRAL |
| Stochastic %D (3) | 40.3 | 40.3 | +0.0 | aynı tanım (%K'nın 3'lü SMA'sı) | — | — |
| Williams %R (14) | -51.3 | -51.3 | -0.0 | aynı tanım (aralık 0 → −50) | Nötr bölge | NEUTRAL |
| CCI (20) | 5.0 | 5.2 | +0.2 | aynı tanım (tipik fiyat, ortalama mutlak sapma, 0.015); eski gösterim 0 ondalık; yeni `fsum` ile düz seride tam 0 | Nötr bölge | NEUTRAL |
| MACD (12,26,9) | 59.8 | 59.8 | -0.0 | EMA tohumu: eski **ilk değer**, yeni **ilk n'in SMA'sı** (StockCharts); 1257 mumda tohum farkı sönmüş | Sinyalin altında | BELOW_SIGNAL |
| MACD sinyal | 80.4 | 80.4 | -0.0 | sinyal EMA'sı ilk 9 geçerli MACD'nin SMA'sıyla tohumlanır | — | hist -20.6 |
| ADX (14) | 21.9 | 22.2 | +0.3 | eski: DX'in 14'lü **basit** ortalaması → yeni: DX de **Wilder** ile yumuşatılır (ilk değer 28. mumda) | Trend güçleniyor | NEUTRAL |
| +DI (14) | 31.0 | 31.0 | -0.0 | oran olduğu için toplam/ortalama Wilder biçimi aynı sonucu verir; eski gösterim 0 ondalık | — | — |
| −DI (14) | 29.0 | 29.1 | +0.1 | aynı (yukarıdaki gibi) | — | — |
| ATR (14) % kapanış | 2.03 | 1.94 | -0.09 | eski: TR'nin 14'lü **basit** ortalaması → yeni: **Wilder** ATR = 86.66 $ | Yüksek oynaklık | NORMAL_VOLATILITY |
| ATR medyan % | 1.15 | 1.85 | +0.70 | eski: **tüm tarih** üzerinden kayan medyan (2021–23'ün düşük ATR%'si tabanı çeker) → yeni: önceki **100** ATR'nin medyanı (82.98 $); oran 1.04 < 1.3 → NORMAL | — | — |
| ROC (12) % | -0.29 | -0.29 | +0.00 | aynı tanım (c/c[−12] − 1)·100 | 12 gün önceye göre aşağıda | NEGATIVE |

Anlamı değişen tek satır **ATR**: değer değil, **etiket**. Eski taban bütün tarihin medyanıydı (%1.15) ve 2021–2023'ün 1.800 $'lık, düşük ATR%'li dönemi tabanı aşağı çektiği için bugünkü oynaklık "yüksek" okunuyordu. Yeni taban önceki 100 günün medyanı (%1.85); bugünkü ATR ona göre 1.04× → NORMAL. Diğer satırlarda fark tanım (RSI +2.0 puan, ADX +0.3) ya da yuvarlama düzeyinde ve bant değişmedi; ADX'te eski "Trend güçleniyor" metni 20–25 bandının eski adıdır, yeni ad NEUTRAL (TRENDING ≥ 25, WEAK_TREND ≤ 20).

Hareketli ortalamalar (SMA/EMA, aynı tanım; EMA200 farkı eski "ilk değer" tohumunun 1057 adımda sönmemiş kalıntısı):

| n | SMA eski | SMA yeni | Δ | EMA eski | EMA yeni | Δ | Fiyat > SMA |
|---|---|---|---|---|---|---|---|
| 5 | 4422.74 | 4422.74 | -7.3e-12 | 4458.29 | 4458.29 | +0.0e+00 | evet |
| 10 | 4507.86 | 4507.86 | -9.1e-13 | 4466.29 | 4466.29 | +0.0e+00 | hayır |
| 20 | 4469.50 | 4469.50 | +0.0e+00 | 4430.47 | 4430.47 | +0.0e+00 | evet |
| 50 | 4239.92 | 4239.92 | +9.1e-13 | 4352.36 | 4352.36 | +0.0e+00 | evet |
| 100 | 4371.22 | 4371.22 | -1.8e-12 | 4372.11 | 4372.11 | -6.7e-10 | evet |
| 200 | 4520.70 | 4520.70 | +0.0e+00 | 4312.80 | 4312.80 | -2.6e-04 | hayır |

En büyük mutlak fark: SMA 7.3e-12, EMA 2.6e-04 $.

### (d) Seans bloğu: derin eşitlik
`technical.session.momentum(intraday.bars, daily=points)` ↔ `momentum_live_20260906.json` (eski `momentum_service` canlı yanıtı, `as_of` 2026-09-04T20:59:58+00:00): **0 fark** (13 üst anahtar: `as_of`, `price`, `direction`, `strength`, `trend`, `support`, `resistance`, `outside_ladder`, `touching`, `breakout`, `ladder`, `components`, `session`; iç içe 92 yaprak değer). Aynı denetim `tests/test_technical_session_fixture.py` içinde alan dışlamadan koşar.

### (e) Kırılım: tek yanlı eski → iki yanlı yeni
| Kaynak | Yan | Hedef | Uzaklık $ | Ulaşma | İtiş | Sönüm | Skor | Etiket |
|---|---|---|---|---|---|---|---|---|
| Eski BE (`momentum_service`) | tek yan: destek | S1 4443.4 (servisin kendi merdiveni) | 33.2 | 1.60 | seans 22 → 0.22 | — | 0.469 | MEDIUM |
| Eski FE (`breakPotential`, Harem çerçevesi, haftalık fib) | yukarı | P 4435.5 | 3.9 | 13.40 | seans 22 → 0.22 | — | 0.469 | MEDIUM |
| Eski FE (`breakPotential`, Harem çerçevesi, haftalık fib) | aşağı | S1 4341.7 | 89.9 | 0.59 | seans 22 → 0.22 | — | 0.359 | MEDIUM |
| Yeni (`analyze_breakout`, GC=F çerçevesi) | yukarı | z-4533 (SWING_LOW, güç 31) 4532.6 | 56.0 | 0.95 | seans 0.22·0.6 + günlük 0.36·0.4 = 0.276 | 0.845 | 0.433 (43) | MODERATE |
| Yeni (`analyze_breakout`, GC=F çerçevesi) | aşağı | z-4354 (SWING_LOW, güç 38) 4353.9 | 122.7 | 0.43 | seans 0.22·0.6 + günlük 0.00·0.4 = 0.132 | 0.810 | 0.194 (19) | WEAK |

Eski cebir `sqrt(min(1, ulaşma) · güç/100)` idi: seans NEUTRAL·22 ile ulaşılabilir her seviye √0.22 = 0.469 → MEDIUM veriyordu — eski BE'nin S1'i ve eski FE'nin P'si aynı 0.469'u taşıyor, hedef farklı olsa da. Yeni formül `sqrt(ulaşma · itiş) · sönüm`; itiş = 0.6·seans + 0.4·günlük ve günlük itiş yalnız skorun (59) 50'nin üstünde kalan yanı, yani **yukarıyı** iter (0.36); aşağı yanda günlük itiş 0. Hedefler artık test edilmiş **bölgeler** (z-4533 güç 31, z-4354 güç 38) ve bölge gücü kırılımı kısıyor (sönüm 0.845 / 0.810). Sonuç: yukarı 43 MODERATE, aşağı 19 WEAK; `headline` None (seans NEUTRAL → öne çıkarılan yan yok), not `NOT_A_PROBABILITY`. Beklenen hareket seansın kalanı için 53.25 $ (`session_remaining`, %1.19).

### (f) Momentum: seans bloğu ↔ günlük bileşik
|  | Eski / seans (korundu, `session.py`) | Yeni / günlük (`momentum_daily.py`) |
|---|---|---|
| Soru | bu seans ilk seviyeyi kırmaya yeter mi (5 dk mum, GC=F) | son haftalar ne kadar tek yönlü ve kararlı (günlük mum) |
| Sonuç | NEUTRAL · 22 · STABLE | NEUTRAL · 59 · WEAK · STRENGTHENING · CONFLICTING |
| Yön kapısı | t = -3.635 ama \|hız\| = 0.16 < 1 → NEUTRAL | skor 59 ∈ (40, 60) → NEUTRAL; uyum 0.28 < 0.5 → CONFLICTING |
| Bileşik | lojistik(\|z\| × uyum) → 22 | z = +0.374; skor = 50 + 50·tanh(z / 2.0) = 59 |
| Bileşenler (σ birimi) | velocity -0.16, acceleration -0.57, rsi -0.10, macd -0.08, drift -0.53, volume -0.86 | velocity -0.71, drift +0.48, rsi +0.57, macd -0.24, adx +0.89, ma +2.73 |
| Ağırlıklar | hız .25 sürüklenme .20 ivme .20 hacim .15 RSI .10 MACD .10 | velocity 0.25 drift 0.20 rsi 0.15 macd 0.15 adx 0.15 ma 0.10 |
| Ölçek | seans σ = %0.1361 (mum getirisi) | σ20 = 0.0145 (günlük log getiri), ATR14 = 86.66 $ |
| Son 3 gün | — | Δ +0, ivme -12, tarihçe [61, 52, 47, 59, 59] |

İki blok **farklı soruya** cevap verir ve ikisi de yanıtta ayrı durur; sayıları karşılaştırmak anlamsız. Bugün ikisi de NEUTRAL diyor ama gerekçe farklı: seans, hız kapısını geçemedi; günlük ise 59 ile eşiğin hemen altında ve bileşenler çelişiyor (hız -0.71 ↔ 50 günlük ortalamadan uzaklık +2.73). Son on günün skorları [84, 85, 82, 82, 73, 61, 52, 47, 59, 59]; `STRENGTHENING` etiketi 3 gün önceki 52 ile bugünkü 59 arasındaki orta noktadan uzaklık farkından (+7 ≥ 3) geliyor.

### (g) Trend: yeni blok ↔ eski arayüz uydurması
| Aralık | n yeni | n eski | Yön | Yön eski | r² | Trend Δ | Gerçekleşen Δ | maks \|Δ\| uydurma alanları | maks \|Δ\| gerçekleşen | maks \|Δ\| çizgi+bantlar |
|---|---|---|---|---|---|---|---|---|---|---|
| gunluk | 90 | 90 | DOWN | DOWN | 0.0863 | %-5.15 | %-1.51 | 8.2e-12 | 0.0e+00 | 1.8e-11 $ (4.3e-15) |
| haftalik | 104 | 104 | UP | UP | 0.8467 | %+96.95 | %+73.42 | 2.6e-11 | 0.0e+00 | 3.8e-11 $ (7.5e-15) |
| aylik | 60 | 60 | UP | UP | 0.8810 | %+203.25 | %+151.07 | 7.3e-12 | 0.0e+00 | 1.1e-11 $ (2.5e-15) |
| ceyreklik | 21 | 21 | UP | UP | 0.8799 | %+191.17 | %+155.03 | 1.4e-17 | 0.0e+00 | 7.3e-12 $ (1.7e-15) |
| yarim | 11 | 11 | UP | UP | 0.9114 | %+187.24 | %+144.96 | 0.0e+00 | 0.0e+00 | 0.0e+00 $ (0.0e+00) |

Beş aralığın tamamında en büyük mutlak fark **2.6e-11** (kayan nokta toplama sırası); yön, r² ve gerçekleşen değişim birebir. Matematik taşınmış, değişmemiştir.

_Betik süresi 0.04 s._
<!-- ta:section:eski-yeni:end -->

<!-- ta:section:backtest:start -->
## Tarihsel destek/direnç tepkisi
Yürüyen pencere: `t` = 300 … 1247 her 5 mumda (190 tarih, 2022-11-11 → 2026-08-21); her `t`'de `analyze_levels(candles[:t], close_t, pivot_levels=yapısal pivotlar(compute_all(candles[:t], today=tarih_t+1)))` — `assemble._structural_pivots` yeniden kullanıldı. Test: sonraki 10 mumda fiyat bölgeye 0.25·ATR_t içine gelir; tepki: temastan sonraki 5 kapanış, HOLD ≥ 1.0 ATR uzaklaşma ve uzak kenarın ötesinde kapanış yok, BREAK uzak kenarın ötesinde ≥ 0.5 ATR kapanış, NONE gerisi. Tutma oranı = HOLD / (HOLD + BREAK).

Sayım: 3866 bölge-gün; 12 onaysız (DEVELOPING) ve 223 `testing` (t anında marj içinde) dışarıda; 2874 bölge 10 mumda test edilmedi, 3 temasın tepki penceresi seride tamamlanmadı; **754 test edilmiş bölge** kaldı (264 HOLD, 340 BREAK, 150 NONE). Plasebo: 5 rastgele seviye/tarih × 190 tarih → 336 test.

### Temel yapılandırma (yarı ömür 90 g, kanat 3, eşikler STRONG ≥ 67 / MODERATE ≥ 34)

| Kesit | n | HOLD | BREAK | NONE | Tutma oranı | NONE payı |
|---|---|---|---|---|---|---|
| Havuz (bütün test edilen bölgeler) | 754 | 264 | 340 | 150 | %43.7 | %20 |
| Plasebo (rastgele seviye, aynı kural) | 336 | 120 | 144 | 72 | %45.5 | %21 |
| T1 (zayıf) [11–25] | 232 | 76 | 123 | 33 | %38.2 | %14 |
| T2 [26–49] | 270 | 86 | 128 | 56 | %40.2 | %21 |
| T3 (güçlü) [50–79] | 252 | 102 | 89 | 61 | %53.4 | %24 |
| Etiket STRONG | 79 | 26 | 33 | 20 | %44.1 | %25 |
| Etiket MODERATE | 307 | 121 | 118 | 68 | %50.6 | %22 |
| Etiket WEAK | 368 | 117 | 189 | 62 | %38.2 | %17 |

Güç ↔ tutma (0/1, NONE hariç) Pearson korelasyonu: 0.128 (n = 604). Güç dağılımı test edilen bölgelerde: ortanca 34, aralık 11–79.

Kesitler (aynı kayıtlar):

| Kesit | n | HOLD | BREAK | NONE | Tutma oranı | NONE payı |
|---|---|---|---|---|---|---|
| Bölge SUPPORT | 302 | 140 | 93 | 69 | %60.1 | %23 |
| Plasebo SUPPORT | 129 | 61 | 39 | 29 | %61.0 | %22 |
| Bölge RESISTANCE | 452 | 124 | 247 | 81 | %33.4 | %18 |
| Plasebo RESISTANCE | 207 | 59 | 105 | 43 | %36.0 | %21 |
| SUPPORT · T1 (zayıf) [12–27] | 99 | 42 | 40 | 17 | %51.2 | %17 |
| SUPPORT · T2 [28–50] | 99 | 43 | 29 | 27 | %59.7 | %27 |
| SUPPORT · T3 (güçlü) [51–79] | 104 | 55 | 24 | 25 | %69.6 | %24 |
| RESISTANCE · T1 (zayıf) [11–25] | 149 | 38 | 91 | 20 | %29.5 | %13 |
| RESISTANCE · T2 [26–47] | 152 | 39 | 87 | 26 | %31.0 | %17 |
| RESISTANCE · T3 (güçlü) [48–79] | 151 | 47 | 69 | 35 | %40.5 | %23 |
| Uzaklık ≤ 2 ATR (t anında) | 407 | 134 | 172 | 101 | %43.8 | %25 |
| Uzaklık > 2 ATR | 347 | 130 | 168 | 49 | %43.6 | %14 |
| Geçmiş temas ≥ 3 | 382 | 133 | 163 | 86 | %44.9 | %23 |
| Geçmiş temas ≤ 1 | 297 | 100 | 148 | 49 | %40.3 | %16 |

Yoğun örneklem (her mum, 948 tarih, pencereler ağır örtüşür — sayı için, bağımsızlık için değil):

| Kesit | n | HOLD | BREAK | NONE | Tutma oranı | NONE payı |
|---|---|---|---|---|---|---|
| Havuz, her mum | 3733 | 1303 | 1671 | 759 | %43.8 | %20 |
| T1 (zayıf) [11–25] | 1116 | 357 | 587 | 172 | %37.8 | %15 |
| T2 [26–49] | 1362 | 470 | 595 | 297 | %44.1 | %22 |
| T3 (güçlü) [50–80] | 1255 | 476 | 489 | 290 | %49.3 | %23 |
| Etiket STRONG | 388 | 120 | 170 | 98 | %41.4 | %25 |
| Etiket MODERATE | 1523 | 586 | 604 | 333 | %49.2 | %22 |
| Etiket WEAK | 1822 | 597 | 897 | 328 | %40.0 | %18 |

### Izgara: `recency_half_life_days` × `swing_wing` (12 yapılandırma, `dataclasses.replace`, paket yapılandırması değişmedi)

| Yarı ömür | Kanat | n test | Tutma STRONG / MODERATE / WEAK | n S / M / W | Tutma T3 / T2 / T1 | Etiket monoton | Dilim monoton | Temel |
|---|---|---|---|---|---|---|---|---|
| 30 | 2 | 768 | %57.7 / %48.7 / %37.7 | 39 / 356 / 373 | %50.3 / %42.5 / %38.5 | evet | evet |  |
| 30 | 3 | 754 | %47.4 / %51.2 / %37.7 | 25 / 333 / 396 | %50.5 / %42.9 / %38.2 | hayır | evet |  |
| 30 | 5 | 713 | %47.1 / %50.2 / %35.7 | 27 / 322 / 364 | %48.7 / %42.0 / %36.6 | hayır | evet |  |
| 60 | 2 | 768 | %48.2 / %47.4 / %39.4 | 80 / 326 / 362 | %53.3 / %39.7 / %38.1 | evet | evet |  |
| 60 | 3 | 754 | %42.6 / %51.2 / %38.1 | 65 / 310 / 379 | %51.8 / %42.3 / %37.4 | hayır | evet |  |
| 60 | 5 | 713 | %47.4 / %49.2 / %36.1 | 55 / 310 / 348 | %49.2 / %43.5 / %34.4 | hayır | evet |  |
| 90 | 2 | 768 | %45.7 / %47.2 / %39.9 | 98 / 317 / 353 | %52.3 / %40.1 / %38.9 | hayır | evet |  |
| 90 | 3 | 754 | %44.1 / %50.6 / %38.2 | 79 / 307 / 368 | %53.4 / %40.2 / %38.2 | hayır | evet | ✓ |
| 90 | 5 | 713 | %49.0 / %48.6 / %35.6 | 71 / 312 / 330 | %50.6 / %41.5 / %35.4 | evet | evet |  |
| 120 | 2 | 768 | %48.8 / %46.3 / %39.7 | 112 / 309 / 347 | %52.6 / %39.8 / %39.0 | evet | evet |  |
| 120 | 3 | 754 | %46.3 / %49.4 / %38.7 | 91 / 302 / 361 | %54.4 / %38.2 / %39.1 | hayır | hayır |  |
| 120 | 5 | 713 | %41.9 / %49.8 / %35.9 | 85 / 304 / 324 | %50.8 / %43.1 / %34.2 | hayır | evet |  |

### İleri bakış kanıtı

10 rastgele `t` için `t` sonrası mumlar ±%20 rastgele ölçeklenip karıştırıldı; `t` anındaki bölge haritası (`Levels` dataclass'ı, bütün alanlar) **10/10** birebir aynı. Aynı boru hattı fonksiyonu (`zones_at(seri, t)`) tam seriyle çağrıldığı için sızıntı olsaydı burada görünürdü.

### Sevk kapısı

- Etiket sırası STRONG > MODERATE > WEAK: **sağlanmıyor** (%44.1 / %50.6 / %38.2)
- Dilim sırası T3 > T2 > T1: **sağlanıyor** (%53.4 / %40.2 / %38.2)
- En zayıf dilim ≥ plasebo tabanı (%45.5): **sağlanmıyor**; ≥ havuz tabanı (%43.7): sağlanmıyor (havuz dilimlerin ağırlıklı ortalaması olduğu için bu ikincisi ancak dilimler ayrışmadığında sağlanır)
- Yan bazında plasebo: destek bölgeleri %60.1 ↔ rastgele destek %61.0; direnç bölgeleri %33.4 ↔ rastgele direnç %36.0 (rejim etkisi: yükselişte destek tutar, direnç kırılır — karşılaştırma yan içinde yapılmalı)
- En güçlü dilim (T3) ≥ plasebo: evet
- Izgarada etiket sırası 4/12, dilim sırası 11/12 yapılandırmada monoton

**Sonuç: kapı kapalı.** Güç sırası tutma oranına tutarlı biçimde yansımıyor; arayüz gücü **betimleyici** göstermeli ("çok test edildi / az test edildi", temas sayısı, son temas tarihi, kaç kaynağın işaret ettiği), "güçlü destek → tutar" iddiası olarak değil.

Örneklem uyarısı: 754 kayıt 190 tarihten geliyor ve aynı bölge ardışık tarihlerde tekrar sayılıyor (5 mumluk adım, 10 mumluk ileri pencere → komşu tarihler örtüşür); bağımsız gözlem sayısı kayıt sayısının çok altında. Repo dersi: 33 örtüşmeyen 30 günlük pencere gürültüydü. Buradaki yüzdeler birkaç puanlık farkı ayırt edemez; yalnız büyük ve ızgara boyunca kararlı farklar anlamlıdır.

_Betik süresi 7.9 s (temel + plasebo 0.9 s, ızgara 4.4 s)._
<!-- ta:section:backtest:end -->

<!-- ta:section:momentum:start -->
## Günlük momentum kovaları
`score_series` 1257 mumda 1223 skor üretti (ısınma 34 mum); ileri getiri için 20 mum kuyruk düşünce **1203 gözlem** (2021-10-25 → 2026-08-07). Ortalama ileri getiri log getiri (%), isabet = (skor − 50) işareti ile ileri getirinin işareti aynı (skor = 50 ve sıfır getiri hariç). Parametreler: z_scale 2.0, UP ≥ 60, DOWN ≤ 40.

### Beşlikler (eşit sayılı, skor sırasıyla)

| Kova | n | ort. 1m | ort. 5m | ort. 10m | ort. 20m | isabet 1m | isabet 5m | isabet 10m | isabet 20m |
|---|---|---|---|---|---|---|---|---|---|
| Q1 [10–36] | 240 | %+0.03 | %+0.20 | %+0.48 | %+1.31 | %46 | %47 | %45 | %38 |
| Q2 [37–51] | 240 | %+0.08 | %+0.28 | %+0.89 | %+1.06 | %46 | %42 | %44 | %41 |
| Q3 [51–65] | 240 | %+0.11 | %+0.65 | %+0.90 | %+1.30 | %52 | %60 | %65 | %58 |
| Q4 [65–77] | 240 | %+0.00 | %+0.35 | %+0.65 | %+1.32 | %54 | %55 | %54 | %63 |
| Q5 [77–93] | 243 | %+0.13 | %+0.37 | %+0.84 | %+2.45 | %58 | %59 | %57 | %72 |

### Etiket aralıkları

| Kova | n | ort. 1m | ort. 5m | ort. 10m | ort. 20m | isabet 1m | isabet 5m | isabet 10m | isabet 20m |
|---|---|---|---|---|---|---|---|---|---|
| [0, 20) | 39 | %+0.04 | %+1.70 | %+2.34 | %+3.90 | %49 | %26 | %28 | %13 |
| [20, 40) | 257 | %+0.05 | %-0.03 | %+0.31 | %+0.90 | %44 | %51 | %48 | %42 |
| [40, 60) | 311 | %+0.10 | %+0.48 | %+0.84 | %+1.24 | %49 | %49 | %52 | %51 |
| [60, 80) | 421 | %+0.06 | %+0.48 | %+0.88 | %+1.49 | %54 | %57 | %58 | %62 |
| [80, 100] | 175 | %+0.09 | %+0.20 | %+0.58 | %+2.26 | %59 | %58 | %56 | %70 |
| Tümü | 1203 | %+0.07 | %+0.37 | %+0.75 | %+1.49 | %51 | %53 | %53 | %54 |

### Spearman ρ (skor ↔ ileri log getiri)

| Ufuk | n (örtüşen) | ρ | t ≈ ρ√((n−2)/(1−ρ²)) | n (örtüşmeyen) | ρ örtüşmeyen |
|---|---|---|---|---|---|
| 1 mum | 1203 | +0.014 | +0.48 | 1203 | +0.014 |
| 5 mum | 1203 | +0.003 | +0.09 | 241 | -0.004 |
| 10 mum | 1203 | -0.004 | -0.13 | 121 | -0.016 |
| 20 mum | 1203 | +0.058 | +2.01 | 61 | +0.039 |

`t` sütunu bağımsız gözlem varsayar; örtüşen pencerelerde **abartılıdır**, yalnız ölçek için yazıldı. Örtüşmeyen sütun her h. gözlemi alır (tek bir faz; başka faz başka sayı verir).

### Skor dağılımı

| Aralık | n | Pay |  |
|---|---|---|---|
| [0, 10) | 0 | %0.0 |  |
| [10, 20) | 39 | %3.2 | ███████ |
| [20, 30) | 109 | %8.9 | ███████████████████ |
| [30, 40) | 148 | %12.1 | ██████████████████████████ |
| [40, 50) | 168 | %13.7 | ██████████████████████████████ |
| [50, 60) | 147 | %12.0 | ██████████████████████████ |
| [60, 70) | 201 | %16.4 | ████████████████████████████████████ |
| [70, 80) | 224 | %18.3 | ████████████████████████████████████████ |
| [80, 90) | 167 | %13.7 | ██████████████████████████████ |
| [90, 100] | 20 | %1.6 | ████ |

Ortalama 56.9, ortanca 60, **sapma 20.48** (tasarım hedefi ≈ 15). Etiket payları: UP %50.0 · NEUTRAL %24.9 · DOWN %25.0.

### `z_scale` taraması (yalnız rapor; yapılandırma değişmedi)

| z_scale | Sapma | Ortalama | UP / NEUTRAL / DOWN | Mevcut |
|---|---|---|---|---|
| 2.0 | 20.48 | 56.9 | %50 / %25 / %25 | ✓ |
| 2.5 | 17.20 | 55.9 | %47 / %31 / %22 |  |
| 3.0 | 14.77 | 55.1 | %43 / %38 / %18 |  |
| 3.5 | 12.89 | 54.4 | %38 / %45 / %16 |  |
| 4.0 | 11.45 | 53.9 | %35 / %50 / %15 |  |

Sapma 15'e en yakın taranan değer z_scale = **3.0** (sapma 14.77); doğrusal ara değerle ≈ **2.95**. Skor = 50 + 50·tanh(z / z_scale) olduğu için z_scale büyüdükçe skor 50'ye sıkışır ve UP/DOWN payı düşer; eşikler (60/40) sabit kalırsa sapmayı 15'e indirmek etiketlerin seyrekleşmesi demektir — ikisi birlikte karar verilmeli.

### Örneklem uyarısı

1203 gözlem **örtüşen** pencerelerden geliyor: 20 mumluk ufukta bağımsız gözlem sayısı ~60, 5 mumlukta ~240. Repo dersi: 33 örtüşmeyen 30 günlük pencere gürültüydü. Kovalar arasındaki birkaç puanlık isabet farkı ya da 0.1'in altındaki ρ, bu örneklemde sıfırdan ayırt edilemez; ancak işaretin ufuklar boyunca tutarlı olması ve büyük kova farkları bilgi taşır. Ayrıca seri 2021–2026 tek bir rejimi (uzun yükseliş) kapsıyor — UP payının yüksekliği kısmen bunun eseri.

_Betik süresi 0.07 s._
<!-- ta:section:momentum:end -->

<!-- ta:section:karar:start -->
## Karar önerileri

Bu bölüm elle yazıldı (2026-09-06); betikler dokunmaz. Her madde bir insan kararı ister; sayılar yukarıdaki bölümlerden.

### 1. Bölge gücü: iddia değil, betimleme (öneri: **betimleyici**)

- Sevk kapısı **kapalı**: etiket sırası STRONG > MODERATE > WEAK sağlanmıyor (%44.1 / %50.6 / %38.2), ızgaranın yalnız 4/12'sinde monoton. Dilim sırası T3 > T2 > T1 ise sağlanıyor (%53.4 / %40.2 / %38.2) ve 11/12 yapılandırmada kararlı — yani **skor** sıralıyor, **etiket eşikleri** (67/34) sıralamıyor.
- Asıl bulgu yan bazında: yükseliş rejiminde herhangi bir destek %60, herhangi bir direnç %33 tutuyor ve **bölge olmak rastgele bir seviyeye üstünlük vermiyor** (destek %60.1 ↔ plasebo %61.0; direnç %33.4 ↔ plasebo %36.0). Skor yan içinde ayrıştırıyor (destek T1 → T3: %51 → %70; direnç %30 → %41) ama en zayıf dilim her iki yanda plasebonun **altında** (kırılımdan yeni çıkmış seviyeler kırılmaya devam ediyor — `break_factor` sönümü bunu doğru kodluyor).
- Sonuç: arayüz "güçlü destek → tutar" demesin. Güvenli sunum **göreli ve betimleyici**: temas sayısı, son temas tarihi, kaç kaynağın işaret ettiği ("3 kez test edildi, son 2 Eylül, salınım + pivot"), gerekirse "bu seride diğer bölgelerden daha çok tuttu". Destek/direnç için **simetrik** bir dil kullanılmamalı; rejim etkisi skorun etkisinden büyük.
- Uyarı: 754 kayıt 190 örtüşen tarihten; birkaç puanlık fark gürültü. Yalnız yan farkı (27 puan) ve yan içi dilim farkı (10–19 puan) sağlam sayılabilir.

### 2. `LevelParams.strong` / `moderate` / `min_strength` (öneri: **şimdilik dondur, etiketi yumuşat**)

- 67 eşiği test edilen bölgelerin yalnız %10'unu (79) STRONG yapıyor ve o grup MODERATE'ten kötü. Tercile sınırları (≈ 26 ve ≈ 50) üç grubu ayrıştırıyor; `strong` ≈ 50'ye çekilirse etiket sırası büyük olasılıkla monoton olur — ama bu **bu seride ölçülmüş** bir eşik olur, 12 yapılandırmalık ızgarada STRONG n'i 25–112 arasında oynuyor. Sayıyı tek seriden dondurmak yerine önce etiket dilini betimleyici yapmak daha ucuz.
- `min_strength` 30: test edilen bölgelerin ortancası 34; eşiğin altındaki bölgeler en düşük tutma dilimine (T1 %38) düşüyor, yön doğru. Değiştirme gerekçesi yok.
- `recency_half_life_days` 90 ve `swing_wing` 3: ızgara hiçbir hücreyi açık kazanan göstermiyor (dilim sırası 11/12'de aynı). Bu kanıtla varsayılanı değiştirmek için sebep yok.

### 3. `MomentumParams.z_scale` ve eşikler (öneri: **birlikte karar ver; tek başına z_scale değiştirme**)

- Skor sapması **20.48**, tasarım hedefi 15; sapmayı 15'e getiren değer **z_scale ≈ 2.95–3.0** (3.0 → 14.77). Ama 60/40 eşikleri sabit kalırsa etiket payları %50/%25/%25'ten %43/%38/%18'e kayar: UP ve DOWN seyrekleşir. Ya z_scale ve `up`/`down` birlikte ayarlanır ya da sapma hedefi 20'ye çekilip mevcut değer kalır.
- Skorun öngörü gücü kısa ufukta **yok**: Spearman ρ 5/10 mumda ≈ 0 (+0.003 / −0.004), 20 mumda +0.058 (örtüşmeyen 61 gözlemle +0.039 — gürültü). Bütün kovalarda ileri getiri pozitif; rejim sürüklenmesi baskın. Uçlar dışında isabet %50 çevresinde.
- İki uç asimetrik ve **zıt**: en yüksek beşlik (77–93) 20 mumda +%2.45 (isabet %72), en düşük etiket aralığı [0, 20) ise +%3.90 ile **ters** (isabet %13, n = 39 — çöküş sonrası toparlanma). Yani düşük skor "aşağı devam" değil, bu seride "dip yakını" olmuş. `DOWN` etiketinin metni bunu iddia etmemeli.
- Öneri: skor "son haftaların yönü ve kararlılığı"nın **betimlemesi** olarak kalsın; `STRENGTHENING/WEAKENING` yalnız skor hareketini anlatsın, getiri beklentisi ima etmesin. Sapma hedefi ürün kararı: 15 istenirse z_scale 3.0 + eşikler yeniden.

### 4. Ürün olarak görünür iki değişiklik (öneri: **onayla ve notla**)

- **Referans çerçevesi**: canlı Harem spot artık seviye hesabına girmiyor; aynı gün aynı merdiven spotta P/S1, kapanışta R1/P veriyordu (P 4435.5 iki fiyatın arasında). Panelde "hesaplama referansı GC=F kapanışı, canlı spot ayrı" notu şart; aksi hâlde okuyucu %1 farkı hata sanır.
- **ATR etiketi**: aynı gün eski arayüz "Yüksek oynaklık" (taban 5 yıllık medyan %1.15), yeni paket NORMAL (taban önceki 100 gün %1.85, oran 1.04). 100 günlük taban bilinçli seçimse `atr_median_window` dondurulmalı; değilse eski tabanın rejim kaymasıyla sistematik "yüksek" verdiği bilinerek karar verilmeli.

### 5. Yeniden ölçüm

- Bu belge 2021–2026 tek rejimli (uzun yükseliş) seride ölçüldü. Rejim değişince yan bazlı tutma oranları ve momentum uçlarının işareti değişebilir; üç betik `config_hash` ve veri hash'iyle yeniden koşturulup bu bölüm güncellenmeli. Ölçüm maliyeti toplam ~9 s.
<!-- ta:section:karar:end -->

