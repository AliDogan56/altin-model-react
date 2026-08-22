# Proje İndeksi

Ons altın (XAU/USD) tahmin ve analiz platformu. React SPA + API Gateway + Market Service +
Model Service. Tahmin, eğitim ve hata ölçümü **yalnız XAU/USD günlük serisine** dayanır;
PAXG/Binance kaynağı ve eski fallback modeli projeden tamamen çıkarılmıştır.

Son tarama: 2026-08-21. Aşağıdaki her sayı o gün ölçüldü.

## Akış

```
Tarayıcı → web nginx (:8080) → api-gateway (:8000) → market-service (:8001)
                                                   → model-service  (:8002)
Canlı ONS / USDTRY / ziynet: tarayıcıdan doğrudan Harem Socket.IO
```

Gateway yalnız yol adına bakar: `/market-service/*` ve `/model-service/*` öneki soyulup
ilgili servise iletilir (`api-gateway/app/services/router_service.py`).

### Uçlar

| Servis | Uç | Not |
|---|---|---|
| market | `GET /v1/market/xau` | xaus.com günlük OHLC, 300 sn önbellek |
| market | `GET /v1/market/fred?id=` | FRED CSV (curl_cffi ile), 900 sn önbellek, son 800 gün |
| market | `GET /v1/market/news` | Google News RSS, 10 başlık |
| model | `GET /v1/features/latest` | **tahmin girdilerinin tek kaynağı** — eğitim setiyle birebir |
| model | `POST /v1/predict` | `{price, features}` → getiri, bant, `feature_effects`, `weights`, `confident`, `clipped_features` |
| model | `GET /v1/learning/metrics` | aktif model + katman dışı metrikler |
| model | `POST /v1/training/run` | elle yeniden eğitim |
| model | `GET /v1/learning/job` | saatlik job durumu |

Model-service'te SQLite yok; `db.py` ve `gold_repository.py` kaldırıldı. Snapshot/observations
tabloları ve `/v1/snapshots` ucu artık mevcut değil.

## XAU/USD veri seti

Üretici: `backend/model-service/app/services/xau_dataset_service.py` →
`backend/model-service/data/xauusd_training_5y.csv`

- Kaynak: `https://xaus.com/api/v1/history` (günlük yüksek/düşük/kapanış)
- FRED serileri her satırın tarihinde bilinen son değerle (`as_of`) eşlenir — sızıntı yok
- Kullanılan FRED serileri: DGS10, DGS2, DFII10, DTWEXBGS, DCOILWTICO, VIXCLS, CPILFESL
- **19 özellik**: 8 teknik (getiri 1/5/20g, 50g ortalamadan sapma, merkezlenmiş RSI, ATR,
  20g oynaklık, 60g zirveden düşüş) + 11 makro (reel faiz 5/20g, dolar 5/20g, breakeven 20g,
  getiri eğrisi, VIX seviye + 5g, çekirdek TÜFE yıllık, petrol 5/20g)
- **Hedefler**: 7, 14 ve 30 takvim günü sonrasının ilk işlem günündeki getirisi
- Henüz vadesi dolmamış hedefler boş bırakılır; ilgili ufkun eğitiminde o satır atlanır
- Güncel dosya: **1197 satır**, 2021-11-16 → 2026-08-21

## Eğitim ve yeniden öğrenme

`backend/model-service/app/services/trainer.py`

- Her ufuk **bağımsız** eğitilir; ortak ağ yok
- Ağ: `MLPRegressor(hidden_layer_sizes=(8, 4), activation="tanh", solver="lbfgs", alpha=0.08)`
- 3 tohumlu (17/42/91) topluluk, tahmin ortalaması
- **Purge'lü genişleyen walk-forward**: katlar %55/%70/%85'te başlar, eğitim penceresi
  `start - horizon` ile kesilir → kat sınırında hedef örtüşmesi temizlenir
- Ölçekleme **yalnız ilgili eğitim katından** hesaplanır
- **Ağırlık kısma**: `weight` = katman dışı tahminin regresyon eğimi, [0, 1]'e kırpılmış
  (merkezlenmiş toplamlarla; ddof karışıklığı yok). Bu ağırlıkla **servis edilen** tahmin
  sıfır-getiri bazını yenemezse ağırlık sıfırlanır ve o ufuk fiilen "tahmin yok" der
- Belirsizlik bandı: ağırlıklı katman dışı artığın **80. yüzdeliği**, tahmin anında
  güncel/eğitim oynaklık oranıyla (0,75–2,0 arası kırpılı) ölçeklenir
- Otomatik job veri setini saatlik tazeler; en az `RETRAIN_EVERY_NEW_ROWS` (varsayılan 5)
  yeni satır oluşunca yeniden eğitir ve `RETRAIN_MINIMUM_ROWS`'u (300) uygular
- **Artefakt `MODEL_DIR` volume'una** yazılır, yanına `active.json` işaretçisi konur ve
  en yeni `KEEP_ARTIFACTS` (5) tanesi saklanır. İmaja gömülen `data/xauusd_model.joblib`
  yalnız volume boşken kullanılan yedektir
- Yüklenen artefaktın `features`/`horizons` listesi koddakiyle birebir doğrulanır;
  uymayan artefakt yüklenmez ve `/v1/learning/job` içinde `rejected_artifacts` olarak raporlanır
- Docker imajı build sırasında sürümlenen CSV'den yedek modeli üretir

### Aktif modelin karnesi (`xauusd-mlp-20260821T164355Z`)

| Ufuk | Etiketli satır | OOF satır | MAE | Yön | Sıfır bazına karşı beceri | Ağırlık |
|---|---|---|---|---|---|---|
| 7g | 1192 | 537 | %2,32 | %63,5 | %3,9 | 0,92 |
| 14g | 1187 | 535 | %3,17 | %62,4 | %1,9 | **0,13** |
| 30g | 1175 | 529 | %4,22 | %70,1 | %26,3 | 0,64 |

Bant genişlikleri (error80): %3,5 / %4,9 / %6,8. 14 günlük ufkun ağırlığı çok düşük —
model orada neredeyse hiçbir şey söylemiyor, bu bilinçli ve doğru davranış.

## Frontend

`frontend/src/` — katmanlı, App.tsx monoliti kaldırıldı. En büyük dosya 383 satır.

```
lib/        saf yardımcılar (math, format, meta) — React bilmez
domain/     saf iş mantığı; model.json'u import etmez, artefakt parametre olarak geçer
services/   ağ katmanı (api/, realtime/, config, http)
features/   ekran bölümleri + veri kancaları (parametre formu kaldırıldı)
components/ paylaşılan bileşenler (SiteNav, SiteFooter, Collapsible, LegalModal)
pages/      DashboardPage, ArticlePage, GuideHubPage, PanelHubPage
app/        App (react-router), routes.ts, ScrollToTop, useDocumentMeta
content/    tek kaynak: makaleler, panel özellikleri, parametre grupları, site metinleri
```

- **Rota**: react-router. `app/routes.ts` uygulama yollarını, `scripts/site-routes.mjs`
  sitemap'i **aynı JSON'lardan** üretir; `routes.test.ts` ikisinin birebir aynı olduğunu doğrular
- **Durum**: `DashboardProvider` (Context). Alt kancalar `useMarketData`, `useForecastModel`,
  `usePanelSettings`, `useFeatureFocus`. Panel durumu yalnız panel rotalarında kurulur —
  rehber sayfaları soket açmaz
- **Tahmin**: `useForecastModel` 700 ms debounce ile `/v1/predict` çağırır. `modelStatus`
  üç değerli: `loading` / `live` / `fallback`. Backend yoksa `data/model.json` devreye girer;
  bu artefakt **nötr** (tüm ağırlıklar sıfır, `fallback: true`) — eski bir ağı çalıştırmaz,
  yalnız geçmiş seriyi ve ölçekleri taşır
- **Yanıt doğrulama**: `services/api/model.ts` → `parseForecast` sunucu yanıtını arayüze
  sokmadan doğrular; bozuk şema `null` döner ve `fallback`'e geçilir
- **Hata sınırı**: her panel bölümü kendi `ErrorBoundary`'si içinde. Sınır yokken bozuk bir
  tahmin yanıtı `forecast.horizons.indexOf(...)` üzerinden fırlıyor ve **tüm sayfayı boşaltıyordu**
- **Ufuk çözümleme**: `domain/model/horizon.ts` → `resolveHorizon`. `Math.max(0, indexOf(x))`
  kalıbı, listede olmayan ufukta sessizce ilk ufka düşüyordu; artık en yakınına düşer ve
  tam eşleşme olup olmadığını bildirir. Katkı kartı ve işlem bölgeleri seçili ufku izler
- **Tazeleme**: `useMarketData` 10 dakikada bir ve sekme yeniden görünür olduğunda
  (5 dakikadan uzun gizli kaldıysa) yeniden çeker; üst üste binen çağrılar engellenir
- **Grafik** (`features/chart/`): viewBox ölçülen piksel kutusuyla birebir (ResizeObserver,
  saran div üzerinde — `<svg>` için ResizeObserver tetiklenmiyor), ölçek tam 1. Sürükle-kaydır,
  iki parmakla ve tekerlekle yakınlaştırma, dokun-sabitle ipucu, ok tuşlarıyla gezinme,
  `<title>/<desc>` + `aria-describedby` ile destek-direnç açıklamasına bağlı
- **Grafik kartı acemi okuyucuya göre sadeleştirildi**: 16 kontrol → 7 (ne kadar geçmiş /
  kaç gün sonrası), 1200px → 1028px. Destek ve direnç artık ince çizgi değil **etiketli
  bölge** (`sr-zone`, fiyatın ±%0,35'i) ve grafiğin altında sade dille anlatılıyor.
  Kaldırılanlar: işlem bölgeleri katmanı (kendi bölümünde duruyor), momentum eşiği,
  zoom düğmeleri, dört efsane anahtarı, günlük tahmin tablosu (karne bölümü bunu
  çok daha geniş örneklemle yapıyor). Modelin geçmiş beklentisi tek bir anahtarla,
  varsayılan kapalı
- **Bölüm sırası DOM sırasıdır.** `_panel-shell.scss` içinde App.tsx monolitinden kalma
  `.content > .chart-block { order:2 }` / `.cards { order:3 }` gibi kurallar vardı; `.content`
  grid olduğu için bunlar DOM sırasını eziyor, **grafik ve tahmin kartları "Ayrıntılar"ın
  altına düşüyordu**. Kurallar kaldırıldı — sıra artık yalnız `DashboardPage`'ten gelir.
  Sıra değişikliği doğrulanırken DOM sırası yetmez, ekrandaki dikey konum ölçülmelidir
- **Parametre formu kaldırıldı.** Sol kenar çubuğu (19 girdinin elle düzenlendiği form) ve
  "Parametreleri göster" düğmesi silindi; girdiler artık `/v1/features/latest`'ten geldiği
  için elle değiştirme anlamını yitirmişti. Yerleşim tek sütun (`.layout{display:block}`),
  `wideChart` durumu ve `resetFields` de kalktı
- **Destek/direnç tek kaynaktan gelir.** Grafik ve pivot kartı aynı `buildLadder` çıktısını
  kullanır; grafikte yedi seviye de kendi adıyla çizilir (S1–S3, P, R1–R3) ve S1/R1 belirgin,
  S3/R3 soluk gösterilir. Önceden grafik `domain/supportResistance.ts` ile fiyatın fiilen
  döndüğü noktaları kümeliyordu; iki bölüm farklı sayı gösterip kafa karıştırıyordu
  (grafik DESTEK $4.529 ↔ pivot P $4.525 gibi). O modül kaldırıldı. Pivot dönemi/yöntemi
  Ayrıntılar'daki karttan seçilir, grafik anında onu izler; varsayılan **haftalık + Fibonacci**.
  Seviyeler `computeDomain`'in **kırpılabilir** kümesinde: S3/R3 fiyattan %10 uzakta
  olabildiği için çekirdek kümeye konsa fiyat çizgisi düz bir hat olurdu (ölçüm: geçmiş
  çizgisi yüksekliğin %64'ünü kullanıyor)
- **Pivot dönemi takvimle belirlenir** (`domain/pivots.ts`). `lastCompletePeriod` koşulsuzca
  sondan bir önceki grubu alıyordu: cuma kapanışı gelmiş olsa bile içinde bulunulan hafta
  "devam ediyor" sayılıyor, seviyeler bir hafta bayat kalıyordu. 22 Ağustos cumartesi kart
  10–14 Ağustos haftasını kullanıyor, altın o günden beri %5 yükseldiği için **R3 dahil tüm
  seviyeler fiyatın altında** kalıyordu. Artık hafta cumartesiden, ay da bittiğinde
  tamamlanmış sayılır; `computePivots(candles, today)` ile test edilebilir
- **Dikey ölçek** (`domain/chart/scale.ts`): belirsizlik bandı çekirdek serileri ezmesin diye
  pay sınırıyla dahil edilir (çekirdek en az %50), taşan uç kırpılır
- Panel sırası — **ana görünüm**: tahmin kartları, ziynet, grafik (özet kartlar ve
  destek-direnç açıklaması grafiğin **altında**); **ayrıntılar**: isabet karnesi, teknik
  göstergeler, pivot, parametre katkısı, TL getirisi, bülten, işlem bölgeleri
  (hepsi `Collapsible` içinde)
- **Vade her yerde `horizonDays`'e bağlı.** Tahmin kartları, grafik, parametre katkısı,
  işlem bölgeleri ve TL getirisi aynı ufku gösterir. TL kartı 3/6/9 **ay** sunuyor ve
  30 günlük tahmini `days/30` kadar üstel olarak uzatıyordu (9 ayda bant ±%32); artık
  yalnız modelin ölçüldüğü 7/14/30 gün. Finansman maliyeti aylık girilir, gün sayısına
  göre bileşik ölçeklenir; taksitli kredi (annüite) formülü kaldırıldı — tek dönemde
  taksit yok. Getiri pozitif değilse başa baş oran **yoktur** (eskiden `%0,00` yazıyordu)
- **İsabet karnesi Ayrıntılar sekmesinde** ve servisten gelir (`/v1/learning/metrics` →
  `services/api/metrics.ts`). Kapalıyken en iyi vadenin isabetini özet olarak gösterir;
  açıldığında vade başına üç sayı: ortalama yanılma, yönü bilme, basit kurala üstünlük.
  Tarayıcı artefaktından üretiliyordu; artefakt nötr yedeğe dönünce (`fallback: true`)
  koşul hiç sağlanmadı ve bölüm **hiçbir dağıtımda görünmedi**. Şimdi her ufuk için
  katman dışı MAE, yön, naif kurala göre beceri ve gün sayısı listelenir
- **Ziynet kartı kaynağın güvenilir alanları üzerine kuruludur** (`domain/ziynet.ts`).
  Harem `dusuk` alanını çeyrek/yarım/tam altında ₺5–₺20 gibi imkânsız değerlerle,
  `kapanis`i ise bayat veriyor; bunlar doğrulanınca (`domain/quotes.ts`) kart neredeyse
  boş kalıyordu. Kart artık her üründe **her zaman** var olan üç şeyden konuşuyor:
  alış, satış ve ürünün saf altın içeriği (`ZIYNET_SPECS`: gram × milyem). Bunlardan
  **ham altın değeri** (canlı ons × USD/TL ÷ 31,1035 × saf gram) ve **işçilik + satıcı
  payı** hesaplanır — ölçülen değerler gram %0,1, ziynet ürünleri %1–2. Gün aralığı ve
  günlük yüzde yalnız kaynağın verisi doğrulanırsa ek bilgi olarak görünür

### Ufuk ağırlıkları

`/v1/predict` her ufuk için `weight` ve `confident` döner. Ağırlığı 0,2'nin altındaki ufukta
ağın katkısı neredeyse tamamen kısılmıştır; çıktı "sıfıra yakın tahmin" değil **"görüş yok"**
olarak sunulmalıdır. Bugünkü örnek: 7g %0,61 (ağırlık 0,92) · 14g %0,06 (**0,13**) · 30g %0,72
(0,64) — ufuklar arası eğri bu yüzden monoton değil.

### Parametre katkısı hakkında

`domain/model/impacts.ts` ve backend'in `feature_effects`'i **ablation** yapar: girdiyi kendi
eğitim ortalamasına çekip çıktı farkını ölçer. Bu bir **model duyarlılığı** ölçüsüdür,
nedensellik ya da "parametre ağırlığı" değildir — ağ doğrusal olmadığı için satırlar toplanmaz.

Kart ("Model Bu Tahmini Neden Verdi?") sade dille konuşur: etkiler **dolar** cinsinden,
*yukarı itenler* / *aşağı çekenler* olarak ayrılmış, her satırda göstergenin ne işe yaradığı
ve bugün sıra dışı olup olmadığı yazılı. Etiketler `content/parameters.ts` → `IMPACT_LABELS`
içinde ve **19 girdinin tamamını** kapsar; eskiden 14'lük bir liste vardı ve en büyük etki
(60 günlük zirveden düşüş) kartta hiç görünmüyordu. Dolar karşılığı 1$'ın altında kalan
satırlar listelenmez ama toplamlara dahildir.

## SEO

- 30 rehber makalesi (`data/seo-articles.json`), 10 panel özelliği (`data/panel-features.json`)
- `scripts/generate-seo-pages.mjs` build sonrası: 30 rehber + `/rehber` dizini + 10 panel
  sayfası + `/panel` dizini + ön render edilmiş anasayfa + **43 URL'lik sitemap**
- **Her rehber, canlı karşılığı olan panel bölümüne bağlanır.** `seo-articles.json` içindeki
  `panel` alanı hedef slug'ı verir; hem `ArticlePage` hem `generate-seo-pages.mjs` bir CTA
  basar. Ön render edilen sürümde bulunması şart — Google'ın indekslediği ve JavaScript
  çalışmadan görülen HTML o. Öncesinde makalelerden panele **tek bir link bile yoktu**
- nginx `absolute_redirect off` + `/panel` ve `/rehber` için ayrı `location =` blokları
  (protokol düşüren 301 sorunu bu yüzden çözüldü)
- `/panel/<slug>` ile gelindiğinde ilgili bölüm açılır, yerleşim durulunca tek yumuşak
  kaydırma yapılır ve kısa süre vurgulanır (`useFeatureFocus`)

## Dağıtım

- `docker-compose.yml`: api-gateway, market-service, model-service, web. Yalnız `web`
  dışarı açık (`127.0.0.1:8080`), TLS host nginx'te (`deploy/nginx/onsaltinanaliz.com.conf`)
- Model imajı proje kökünden build edilir (CSV'yi kopyalayabilmek için)
- Sunucu ve deploy adımları: [[altin-model-deployment]] (hafıza)

## Test

```
frontend: 13 dosya, 85 test (vitest: domain + lib + app/routes + services)
backend : model-service 23 test (pytest)
```

Vitest bu Node sürümünde `.bin/vitest` sarmalayıcısıyla çalışmıyor:
`node node_modules/vitest/vitest.mjs run` kullan.

## Bilinen sorunlar ve temizlik borcu

1. **Harem `kapanis` alanı güvenilmez.** Ziynet kartlarındaki günlük yüzde bundan hesaplanıyor
   ve bayat kapanışla yanlış çıkabiliyor; mevcut asimetrik guard bazı ürünleri kaçırıyor.
   Ayrıntı: [[altin-fred-parse-ve-harem-kapanis]]
2. Rafa kaldırılan iş: "altını ne itti/çekti" sürücü panosu — [[surucu-panosu-rafta]]

### 2026-08-21 frontend loop'unda kapatılanlar

- **Bozuk `/v1/predict` yanıtı tüm sayfayı beyaza düşürüyordu** (deneyle doğrulandı: gövde
  0 karakter). Artık `parseForecast` reddediyor ve bölüm bazlı `ErrorBoundary` var.
- `services/config.ts` modül yüklenirken `window.location` okuyordu; tarayıcı dışı her
  ortamda import anında patlıyordu. Adresler artık çağrı anında çözülür.
- Backend'in `weights`/`confident` alanları kullanılmıyordu; ağırlığı 0,13 olan 14 günlük
  ufuk gerçek tahmin gibi gösteriliyordu. Artık **"Görüş yok"** yazıyor.
- Parametre katkısı ve işlem bölgeleri sabit 30 güne bağlıydı; kullanıcı 7 güne geçse bile
  kart 30 günü anlatmaya devam ediyordu.
- Varsayılan ufuk 14 idi — modelin görüş bildirmediği vade. 30 güne alındı.
- Veriler yalnız sayfa açılışında çekiliyordu; gün boyu açık sekme bayat girdi gösteriyordu.
- `strict: false` idi; `noImplicitAny` + `strictNullChecks` + `strictFunctionTypes` +
  `noUnusedLocals` açıldı ve 81 gizli tip hatası giderildi (`vite.config.ts` kapsam dışı).
- `LegalModal` `aria-modal` diyordu ama odak yönetimi yoktu: odak tuzağı ve kapanışta
  çağıran öğeye geri dönüş eklendi.
- Ölçüldü, kusur değil: canlı tick başına ~90 DOM mutasyonu var ama 12 saniyede **0 uzun
  görev** — fiyat çizgisi, fiyat kartı ve ziynet kartları gerçekten güncelleniyor.

### 2026-08-21 model-service loop'unda kapatılanlar

- Tarayıcı model girdilerini kendi hesaplıyordu ve 19 alanın **10'u** eğitim setinden farklı
  çıkıyordu (makro `*_5d` gözlem sayısıyla, `*_20d` yanlış çapa tarihiyle geriye bakıyordu).
  Girdiler artık `/v1/features/latest`'ten gelir; tarayıcı FRED indirmez.
  Bunun yan etkisi olarak `parseCsv`'nin boş FRED alanını 0 sayma hatası da ortadan kalktı
  (kodun tamamı silindi: `lib/series.ts`, `domain/market/goldFeatures.ts`, `macroFeatures.ts`).
- Yeniden eğitilen model kalıcı değildi: artefakt imajın içine yazılıyor, `MODEL_DIR` volume'u
  hiç kullanılmıyor, `active.json` hiç üretilmiyordu. Her container restart'ında eğitim kayboluyordu.
- Artefakt şeması doğrulanmıyordu; `RETRAIN_MINIMUM_ROWS` ölü konfigdi; `_load_dataset` eksik
  sütunu bildirmiyordu; `train_model` yok sayılan parametreler taşıyordu; `training_rows`
  anahtarı sabit `"7"` idi; ağırlıkta `cov(ddof=1)/var(ddof=0)` karışıktı; ufuk devre dışı
  bırakma kararı ham beceriye bakarken rapor ağırlıklı beceriyi yazıyordu.
- Ölü dosyalar silindi: `app/schemas.py`, `data/initial_model.json` (86 KB),
  `data/gold_model_localhost.sqlite3`. `on_event` yerine `lifespan` kullanılıyor.

## Komutlar

```bash
backend/model-service/.venv/bin/python backend/model-service/scripts/build_xau_dataset.py
backend/model-service/.venv/bin/python -c "from app.services.trainer import train_model; print(train_model())"
backend/model-service/.venv/bin/python -m pytest backend/model-service/tests
backend/model-service/.venv/bin/python backend/model-service/scripts/export_frontend_fallback.py
cd frontend && node node_modules/vitest/vitest.mjs run
docker compose up -d --build
```
