# Proje İndeksi

Ons altın (XAU/USD) tahmin ve analiz platformu. React SPA + API Gateway + Market Service +
Model Service. Tahmin, eğitim ve hata ölçümü **yalnız XAU/USD günlük serisine** dayanır;
PAXG/Binance kaynağı ve eski fallback modeli projeden tamamen çıkarılmıştır.

Son tam tarama: **2026-09-06**. Her sayı o gün ölçüldü; daha eski tarih taşıyan
bölümler o günkü ölçümü anlatır. 5 Eylül'de iki büyük değişiklik girdi ve ikisi de
canlıda: pano **sekmeli çalışma alanına** geçti (`033e9eb`, bkz. "Sekmeli çalışma
alanı") ve model servisi **aday–şampiyon akışına** geçti (`8443c0f`, bkz. "Aday–şampiyon
akışı ve denetim"). Bu ikisini bilmeden eski bölümler yanıltır.

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
| market | `GET /v1/market/xau` | xaus.com günlük OHLC, 300 sn önbellek, **yedek kaynaklı** |
| market | `GET /v1/market/fred?id=` | FRED CSV (curl_cffi ile), 900 sn önbellek, son 800 gün |
| market | `GET /v1/market/news` | Google News RSS, 10 başlık |
| market | `GET /v1/market/xau/intraday` | Yahoo 5 günlük 5 dakikalık mumlar, 60 sn önbellek |
| market | `GET /v1/market/xau/technical` | **tüm teknik analiz** (referans, mumlar, göstergeler, 27 pivot seti + başlık merdiveni, bölgeler, günlük momentum, seans, kırılım, trend); `?pivot_method=classic|fibonacci|camarilla&pivot_period=daily|weekly|monthly&include=<blok listesi>`; ETag = önbellek anahtarı; 142 KB ham / 41 KB gzip, `include=pivots,breakout` 2 KB |
| market | `GET /v1/market/xau/momentum` | **kullanımdan kalkıyor** (`Deprecation: true`): aynı analizin `session` bloğu, eski gövdeyle bayt-uyumlu; 503 mesajları korunur |
| model | `GET /health` · `GET /ready` | `ready` model yokken **503** `MODEL_UNAVAILABLE` |
| model | `GET /v1/features/latest` | **tahmin girdilerinin tek kaynağı**; `dataset_hash`, `feature_version`, `provenance`, `validation_status` (canlıda `UNVERIFIED_PROVENANCE`) |
| model | `POST /v1/predict` | `{price, features, source_date?}` → getiri, bant, `feature_effects`, `weights`, `confident`, `no_view_reasons`, `status`, `intervals`, `model_disagreement`, `ood`, `base_price`, `forecast_kind` (her zaman `client_scenario`) |
| model | `GET /v1/learning/metrics` | aktif model + metrikler + `evaluation_version` (eski artefaktta `null`) |
| model | `GET /v1/learning/job` | saatlik job durumu, `new_labels_by_horizon` |
| model | `POST /v1/training/run` | **admin** (Bearer `MODEL_ADMIN_TOKEN`); aday eğitir, terfi etmez. Token yoksa **503** — canlıda böyle |
| model | `POST /v1/forecasts/canonical` | admin; doğrulanmış PIT sağlayıcı ister → mevcut veri setiyle **her zaman reddeder** |
| model | `GET /v1/monitoring` | tahmin defteri özeti; `PREDICTION_LOGGING` kapalıyken `DISABLED` (canlıda böyle) |

Model-service'te yalnız **isteğe bağlı** SQLite var: `prediction_ledger.py` tahmin defteri
(`PREDICTION_LOGGING=true` olmadan hiç oluşmaz). Eski `db.py`, `gold_repository.py`,
`/v1/snapshots` yok.

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

## Fiyat kaynağı ve yedeği

Birincil kaynak `xaus.com/api/v1/history`. **2026-08-31'de bir saatten uzun 503
döndü**; `/v1/market/xau` 502 verdi (grafik boş kaldı) ve model-service'in saatlik
job'u `HTTP Error 503` ile düştü (veri seti dondu). İki yol da aynı kaynağa
doğrudan bağlıydı.

Artık ikisinde de yedek var: `query1.finance.yahoo.com/.../GC=F?range=5y&interval=1d`.

- Yedek gövdeyi birincil kaynağın şemasına çevirir (`d, c, h, l`); tüketicilerde
  değişiklik gerekmedi. market-service yanıta `source` ve `fallback` alanları ekler
- **Kaynak harmanlanmaz**: yedeğe düşüldüğünde serinin tamamı Yahoo'dan gelir,
  yani seri kendi içinde tutarlıdır — spot ile vadeliyi uç uca eklemek yok
- `GC=F` vadeli fiyat; spot'tan ~%0,6 farklı. 19 girdinin tamamı getiri/oran
  olduğu için model seviye farkından etkilenmez
- Eksik günler (boş `close/high/low`) atlanır, satırlar tarih sırasına sokulur
- Testler: market-service `test_xau_fallback.py` (8), model-service
  `test_dataset_fallback.py` (10)

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
- Otomatik job veri setini saatlik tazeler ve **her ufuk için olgunlaşmış yeni etiket**
  sayar (referans: aktif modelin ve son adayın `training_end`'i). Beş yıllık kayan
  pencerede satır sayısı sabit kalırken etiketler ilerler; o yüzden satır artışı değil
  etiket tarihi sayılır. Ufukların **en azı** `RETRAIN_EVERY_NEW_ROWS` (5) olunca ve veri
  seti hash'i değişmişse **aday** eğitir; `RETRAIN_MINIMUM_ROWS` (300) uygulanır.
  Eğitilen aday şampiyonu **değiştirmez** (bkz. aday–şampiyon akışı)
- **Build sırasında eğitim yapılmaz.** Dockerfile önceden imaja bir model gömüyordu;
  sonucu şuydu: imaj her kurulduğunda model yeniden eğitiliyor ve hangi ufukların açık
  olduğu değişebiliyordu — yani modeli eğitim takvimi değil **deploy takvimi**
  belirliyordu. 2026-09-03'te bir frontend dağıtımı 7 günlük ufku sessizce kapattı
  (ağırlık 0,92 → 0,00). Eğitim artık yalnız `automatic_learning_service`'te
- **Soğuk açılış:** model yokken `previous_rows = 0` olduğu için eşik kendiliğinden
  aşılır ve iş ilk turunda (başlangıçtan 2 sn sonra) eğitir. İzole konteynerde ölçüldü:
  **6. saniyede** model hazır ve `/models` içine `active.json` + artefakt yazılmış;
  yeniden başlatmada aynı sürüm volume'dan okundu, yeniden eğitilmedi. O ~6 saniyelik
  boşlukta `/v1/predict` **503** döner ve arayüz nötr yedeğe düşer
- Yan fayda: artefakt kalıcılığı da bu değişiklikle fiilen çalışır hâle geldi; önceden
  `/models` boş kalıyor ve servis her açılışta imaja gömülü modele düşüyordu
- **Artefakt `MODEL_DIR` volume'una** yazılır, yanına `active.json` işaretçisi konur ve
  en yeni `KEEP_ARTIFACTS` (5) tanesi saklanır. İmaja gömülen `data/xauusd_model.joblib`
  yalnız volume boşken kullanılan yedektir
- Yüklenen artefaktın `features`/`horizons` listesi koddakiyle birebir doğrulanır;
  uymayan artefakt yüklenmez ve `/v1/learning/job` içinde `rejected_artifacts` olarak raporlanır
- İmaj build'inde eğitim yok (yukarıda). `data/xauusd_model.joblib` repoda duran eski
  yedek; loader `MODEL_DIR/active.json` → imaj yedeği sırasıyla bakar

### Aktif modelin karnesi (`xauusd-mlp-20260903T201722Z`, canlı, 2026-09-06)

| Ufuk | OOF satır | MAE | Yön | MSE beceri | Ağırlık | Görüş |
|---|---|---|---|---|---|---|
| 7g | 537 | %2,43 | — | %0,0 | **0,00** | yok |
| 14g | 535 | %3,16 | %62,1 | %2,1 | 0,14 | yok (<0,2) |
| 30g | 529 | %4,53 | %70,1 | %17,0 | 0,37 | var |

Bu, 3 Eylül soğuk açılışında eğitilen **eski akış** artefaktı (`evaluation_version: null`,
`input_policy` legacy). **7 günlük ufuk kapalı** — aynı verinin yeniden eğitimi ağırlığı
0,92'den 0,00'a düşürdü; yani 7g becerisi eğitim tohum/kesitine bu kadar duyarlı.
Arayüz varsayılanı 30 gün olduğu için sayfa açılışında görüş var. Yeni akışta bu model
**otomatik değişmez** (aşağıda).

## Aday–şampiyon akışı ve denetim (2026-09-05, `8443c0f`)

5 Eylül'de model servisi baştan sona bir denetimden geçti; sonuç `docs/model-audit/`
(FEATURE_AUDIT.md, OPERATIONS.md — İngilizce) ve `reports/model-audit-20260905/` (9,7 MB,
repoya işlenmiş; paket 45 MB). Tek cümleyle: **eğitim artık aday üretir, şampiyonu kimse
otomatik değiştirmez ve terfi için kod yolu yoktur.**

- `train_model(promote=True)` **hata fırlatır**; aday `xauusd-mlp-candidate-…` adıyla
  `MODEL_DIR`'e yazılır, `active.json` dokunulmaz, `promotion_status: REVIEW_REQUIRED`.
  Budama şampiyonu asla silmez. Terfi = operatörün `active.json`'ı elle yazması; loader
  artefaktı doğrular (scaler sonlu/pozitif, ağ boyutu, ağırlıklar sonlu, sürüm)
- `assert_promotion_ready` doğrulanmış PIT **spot** kaynak ister; mevcut CSV'nin manifesti
  `availability: unverified`, `macro_vintage: current_revision`, `validated: false` →
  **terfi kapısı bu veri setiyle kapalı.** Yani şampiyon, veri kaynağı değişmeden hiç
  yenilenmeyecek. Bu bilinçli: denetim FRED gözlem tarihinin yayın tarihi olmadığını,
  CPI'da artık-yıl referans ayı hatasını (8 ay-sonu sızıntısı) ve yedek `GC=F`'in spot
  olmadığını belgeledi
- **Yeni modüller** (`app/services/`): `data_quality` (fail-closed doğrulama, manifest
  SHA-256; `feature_vector` 19'lu sırayı eğitim ve servis için tek yerden verir),
  `preprocessing` (`standard-clip-v1`: yalnız eğitimden ölçek + ±6 kırpma, eğitim ve
  servis aynı fonksiyonu kullanır — eskiden kırpma yalnız serviste vardı), `temporal_validation`
  (`nested-purged-v1`: kat = eğitim → ağırlık kalibrasyonu → aralık kalibrasyonu → dış test,
  hedef olgunlaşmasıyla purge; ≥100 bağımsız test satırı şart), `point_in_time` (çevrimdışı,
  yayın/vintage damgalı makro kurucu; canlıya bağlı **değil**), `prediction_ledger` (isteğe
  bağlı append-only SQLite, trigger'larla değişmez), `controllers/admin_auth` (boş token =
  yönetim uçları 503)
- **Metrik sözlüğü değişti**: `direction` yalnız ağırlık ≥ 0,2 ve sıfır olmayan
  getirilerde (`directional_rows`, `active_fraction` yanında), `mae_skill_vs_zero` yeni,
  `skill_vs_zero` MSE bazlı eski ad, `empirical_coverage` .5/.7/.8/.9 yüzdelikleri için
  dış-test kapsamı, `active` = ağırlık ≥ 0,2 (eskiden > 0). Eski ve yeni ölçüm
  **karşılaştırılamaz**; arayüz karnede `skillBasis` (MAE/MSE) ve eski ölçüm notu gösterir
- **Servis yanıtı**: her `/v1/predict` bir `client_scenario`; `source_date` verilmezse
  `INSUFFICIENT_DATA`, 7 takvim gününden eskiyse `STALE_DATA` ve tüm ufuklar görüşsüz.
  Eski artefakt `legacy-clip-and-frozen-neutralization` politikasını korur (donmuş girdi
  nötrleme hâlâ çalışır); aday artefaktlar `canonical-asof-no-neutralization-v1` ile
  **nötrleme yapmaz**. İstek boyunca tek artefakt referansı tutulur, reload ufukları
  karıştıramaz. `ood` z-skorları tanısaldır, ağırlığı değiştirmez
- Frontend tarafı: `requestForecast` `source_date` gönderir ve özellik tarihi gelmeden
  istek atmaz; tahmin `base_price`'a (günlük kapanış) bağlanır, canlı spot ayrı gösterilir
  ("Hesaplama referansı" satırı). Bant etiketi sunucunun `nominal_coverage`'ından gelir
  ("%80 nominal aralık · canlı kapsam ölçülmedi"); eski %70 ve normal-dağılım çevrimi kalktı
- Araştırma: `research/evaluation.py` (11 spesifikasyon × 3 ufuk, blok bootstrap, konformal
  kapsam) ve `scripts/run_model_audit.py` / `summarize_` / `render_` / `verify_model_audit.py`.
  Özet (`reports/…/summary.csv`): **7g'de hiçbir yöntem persistence'ı geçmiyor** (iç içe
  MLP beceri 0), 30g'de iç içe MLP yalnız %33 aktif ve orada yön %77,8, MAE becerisi %4,7;
  `direction_logistic` 30g MAE becerisi %9,5 ile en iyi. Çalıştırma ağ, canlı yazma ve
  terfi yapmaz
- Ortam: `MODEL_ADMIN_TOKEN` (boş → yönetim kapalı), `PREDICTION_LOGGING` (false),
  `PREDICTION_LOG_PATH`. Compose hiçbirini set etmez; canlı böyle çalışıyor

## Frontend

`frontend/src/` — katmanlı, App.tsx monoliti kaldırıldı. En büyük dosya `ForecastChart.tsx` 406 satır; backend'de `momentum_service.py` 535.

```
lib/        saf yardımcılar (math, format, meta) — React bilmez
domain/     kalan saf mantık: model/ (tahmin sunumu), chart/scale.ts (render geometrisi), loan/ziynet/quotes
            (Harem'e bağlı). Teknik analiz (pivot, gösterge, trend, bölge, momentum) BURADA DEĞİL — backend
services/   ağ katmanı (api/, realtime/, config, http)
features/   ekran bölümleri + veri kancaları (parametre formu kaldırıldı)
components/ paylaşılan bileşenler (SiteNav, SiteFooter, Collapsible, LegalModal, Spinner)
components/ui/  DataTimestamp, InfoTooltip (details/summary), SegmentedControl (radiogroup)
pages/      DashboardRoute (sağlayıcı + panel, tembel), DashboardPage, ArticlePage,
            GuideHubPage, PanelHubPage, SitePageView
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
- **Yazı tipi bilinçli sistem yığını; web font yüklenmez.** Önceden `Inter` bildiriliyor
  ama hiçbir yerde yüklenmiyordu (ölçüldü: `document.fonts.size = 0`). Sonuç, Inter'in
  kurulu olduğu makinede bir yüz, Android ve Windows'ta başka bir yüzdü — marka yazı tipi
  kullanıcıların çoğuna hiç ulaşmıyordu (trafiğin %76'sı mobil, çoğu Android). Sistem
  yığını seçildi çünkü sitenin birinci sorunu yük ve Inter marka karakteri katmayan bir
  varsayılan; maliyeti ödeyip özgünlük kazanılmıyordu. Karakter istenirse doğru yer gövde
  değil, **başlıklar için ayrı bir display yüz**. Sıra platformun kendi arayüz yüzünü
  önceler ve hepsi Türkçe diyakritikleri karşılar. Doğrulandı: sıfır font ağ isteği,
  375 ve 780 px'te HTML kırpılması 0, gövde taşması 0
- **İki tema var, varsayılan aydınlık.** Palet `styles/_tokens.scss` içinde **74 token**
  olarak tanımlı (5 Eylül'de yeniden yazıldı, açıklama yorumları silindi); aydınlık palet `:root`'ta, koyu palet `:root[data-theme="dark"]`'ta ve
  ikisi birebir aynı anahtarları taşır. Sistem tercihine göre otomatik geçiş **yok** —
  varsayılanın aydınlık olması ürün kararı. Seçim `localStorage['oaa-theme']`'de saklanır;
  `index.html` içindeki satır içi betik damgayı **ilk boyamadan önce** basar (React'e
  bırakılırsa koyu tema seçen kullanıcı bir kare aydınlık ekran görüyor)
- **SCSS'te sabit renk yok.** 324 kullanım token'a çevrildi; `_tokens.scss` dışında hiçbir
  dosyada hex kalmadı. Alfalı renkler `-rgb` üçlüsü üzerinden kullanılır
  (`rgb(var(--surface-rgb) / .67)`) — böylece yarı saydam katmanlar özgün alfasını korur
- **Renk geçişi (`transition:color` / `border-color`) kullanılmıyor.** Özel değişkene bağlı
  renk geçişi tema değişiminde hesaplanan değeri **bir tema geriden** bırakıyor (Chrome;
  ziynet fiyatı ve tahmin kartı kenarlığında ölçüldü). `.theme-switching` sınıfı geçişi
  bastırıyor ama sınıf kalkınca hata geri geliyordu; çözüm renk geçişini kaldırmak oldu.
  Ziynet tik parlaması zaten `@keyframes` ile yapılıyor
- **Yükleme göstergesi projeye özgü** (`components/Spinner.tsx` + `styles/_spinner.scss`):
  uygulama ikonundaki altın sikke aşağıdan yukarı **doluyor**, üstünde ikonun analiz oku
  çiziliyor, kenarında dönen yay var. Boyutlar `xs 12 / sm 16 / md 22 / lg 44`; 16 pikselin
  altında ok çamura döndüğü için gizlenir. Gradyan ve kırpma yolu kimlikleri `useId` ile
  üretilir — sabit id'ler aynı sayfadaki ikinci spinner'ı dolgusuz bırakıyordu
- **Spinner en az bir dolum boyunca ekranda kalır** (`lib/hold.ts` + `app/useMinVisible.ts`).
  Veri 80 ms'de gelince gösterge tek karede görünüp kayboluyor, dolum hiç okunmuyordu.
  Asgari süre 1150 ms — `spinner-fill` döngüsünün sikkenin dolduğu anı. Karar mantığı saf
  ve test edilir (`hold.test.ts`, 8 test); kanca yalnız ince bir sarmalayıcı.
  Ölçüldü: tamponsuz tek kare → tamponla ~1 sn.
  **Tuzak:** `nextHold` değişiklik yokken **aynı nesneyi** döndürmeli. Yeni nesne dönmek,
  durumu effect içinde güncelleyen kancada sonsuz render döngüsü yaratıyor
  (React #185, "Maximum update depth exceeded"); grafik ilk yüklemede bu yüzden patladı.
  `hold.test.ts` bunu nesne kimliğiyle doğrular
- **Spinner nerede dönüyor** (5 Eylül sonrası daraldı): rota yüklenirken sayfa yedeği,
  rehber yüklemesi ve bölüm içi bekleyişler. Panel başlığı spinner kullanmaz, boş değeri
  "—" ve `DataTimestamp` durumuyla ("Veri bekleniyor / Canlı / Gecikmeli veri") anlatır
- **Kontrast ölçülüyor.** Her iki temada tüm görünür metinler WCAG AA'ya göre denetlendi
  (anasayfa 418, rehber 132, kurumsal 59 öge): sıfır hata. Aydınlık temada `--text-dim`,
  `--gold`, `--teal`, `--blue` bu denetim sonucu koyulaştırıldı
- **`.skip-link` özgüllük hatası düzeltildi**: `.site-nav a` rengi eziyordu, atlama bağlantısı
  altın zemin üzerinde okunmuyordu (koyu temada kontrast 1,13)
- **Bölüm sırası DOM sırasıdır** (tarihçe: `_panel-shell.scss`'teki `order` kuralları
  grafiği "Ayrıntılar"ın altına düşürüyordu, kaldırıldı). Sıra değişikliği doğrulanırken
  DOM sırası yetmez, ekrandaki dikey konum ölçülmelidir — sekmeli düzende ayrıca sekmenin
  görünür olduğu da ölçülmeli
- **Parametre formu kaldırıldı.** Sol kenar çubuğu (19 girdinin elle düzenlendiği form) ve
  "Parametreleri göster" düğmesi silindi; girdiler artık `/v1/features/latest`'ten geldiği
  için elle değiştirme anlamını yitirmişti. Yerleşim tek sütun (`.layout{display:block}`),
  `wideChart` durumu ve `resetFields` de kalktı
- **Grafikte mum görünümü var** (`domain/chart/candles.ts` + `ForecastChart`).
  **Veri kısıtı:** fiyat kaynağı (xaus.com) yalnız tarih, kapanış, gün içi yüksek ve
  düşük veriyor — **açılış yok** (uçtan doğrulandı: alanlar `d, c, h, l`). Bu yüzden
  gövde "açılış → kapanış" değil **önceki kapanış → kapanış**, yani günün net hareketi;
  fitil ise gerçek gün içi aralık. Her sayı ölçülmüş veridir, farklı olan gövdenin
  tanımıdır ve grafiğin altında düz dille yazılıdır
- **Mum modu ayrıntıları**: `Görünüm: Çizgi / Mum` anahtarı, varsayılan çizgi (acemi
  okuyucu için sade). Fitiller `computeDomain`'in çekirdek kümesine katılır, yoksa
  kırpılırlardı. Mum genişliği gün başına pikselden türer, 1–14 px arası kırpılı
  (1 yılda 2,55 px, 1 ayda 12,5 px — ölçüldü). `candles` boşken (servis erişilemez)
  mum düğmesi kapalı ve grafik çizgiye düşer; aksi hâlde grafik bomboş kalıyordu.
  İpucu kartı mum modunda **gün içi aralık** satırı ekler ve altındaki karşılaştırma
  satırlarını 21 px kaydırır
- **Mobilde tek parmak seçim yapar, kaydırmaz.** Önceden tek parmak grafiği kaydırıyordu
  ve bir günün değerini görmek için **tam o güne dokunmak** gerekiyordu; 90 mumun 250
  piksele sığdığı ekranda gün başına ~3 piksel düşüyor, bu pratikte imkânsızdı. Artık
  parmağı gezdirmek imleci gün gün taşır ve ipucu açık kalır. Kaydırma ve yakınlaştırma
  **iki parmağa** taşındı (orta noktanın kayması kaydırma, açıklığın değişmesi zoom)
- **Yakınlaştırılmışken kaydırmanın üç yolu var**: iki parmakla sürükleme; tek parmakla
  çizim alanının kenarına (34 px) gitmek — orada grafik kendiliğinden kayar; ve gün
  gezinme çubuğunun okları (`focusPoint` seçim pencereden çıkınca kaydırır)
- **Gün gezinme çubuğu** (`.day-stepper`): imleç sabitlendiğinde grafiğin altında
  `‹ tarih › Kapat` olarak çıkar, dokunmatik hedefleri 34 px. Sürükleme kabaca yaklaştırır,
  oklar tam güne oturtur; klavye okları da aynı `step`'i kullanır.
  **Tuzak:** çubuk SVG'nin dışında olduğu için "dışarı dokunma sabitlemeyi bozar" kuralı
  düğmelere basınca ipucunu kapatıyordu; hareket kancasına `keepRef` (chart-wrap) eklendi
- **Canlı fiyat grafikte kendi çizgisiyle işaretli.** Önce yalnız 5 piksellik bir nokta
  vardı (aydınlık temada `--teal` koyu yeşil) ve mum modunda çizgi gizlendiği için anlık
  fiyat hiç okunmuyordu. Artık: plot boyunca **kesikli yatay çizgi** (2 px, 7-5 desen,
  `--teal-fill`), sol ucunda **CANLI** etiketi, noktada atan hale (`now-pulse`, `scale`
  ile — CSS'te SVG `r` her tarayıcıda canlandırılamıyor) ve efsanede kendi anahtarı.
  Destek çizgileri de yeşil olduğu için ayrım **kesikli desen + etiket + kalınlık**la
  yapılır; CANLI etiketi çizginin **altına** yazılır, S/R etiketleri üstte durur
- **Destek/direnç tek kaynaktan gelir** (2026-09-06'dan beri kaynak backend `pivots.headline.ladder`
  ve `levels.zones`; `buildLadder` FE'den silindi). Grafik ve pivot kartı aynı merdiveni
  kullanır; grafikte yedi seviye de kendi adıyla çizilir (S1–S3, P, R1–R3) ve S1/R1 belirgin,
  S3/R3 soluk gösterilir. Önceden grafik `domain/supportResistance.ts` ile fiyatın fiilen
  döndüğü noktaları kümeliyordu; iki bölüm farklı sayı gösterip kafa karıştırıyordu
  (grafik DESTEK $4.529 ↔ pivot P $4.525 gibi). O modül kaldırıldı. Pivot dönemi/yöntemi
  Ayrıntılar'daki karttan seçilir, grafik anında onu izler; varsayılan **haftalık + Fibonacci**.
  Seviyeler `computeDomain`'in **kırpılabilir** kümesinde: S3/R3 fiyattan %10 uzakta
  olabildiği için çekirdek kümeye konsa fiyat çizgisi düz bir hat olurdu (ölçüm: geçmiş
  çizgisi yüksekliğin %64'ünü kullanıyor)
- **Pivot dönemi takvimle belirlenir** (artık backend `candles.previous_completed_period`; eski `domain/pivots.ts` silindi). `lastCompletePeriod` koşulsuzca
  sondan bir önceki grubu alıyordu: cuma kapanışı gelmiş olsa bile içinde bulunulan hafta
  "devam ediyor" sayılıyor, seviyeler bir hafta bayat kalıyordu. 22 Ağustos cumartesi kart
  10–14 Ağustos haftasını kullanıyor, altın o günden beri %5 yükseldiği için **R3 dahil tüm
  seviyeler fiyatın altında** kalıyordu. Artık hafta cumartesiden, ay da bittiğinde
  tamamlanmış sayılır; `computePivots(candles, today)` ile test edilebilir
- **Dikey ölçek** (`domain/chart/scale.ts`): belirsizlik bandı çekirdek serileri ezmesin diye
  pay sınırıyla dahil edilir (çekirdek en az %50), taşan uç kırpılır
- Panel yerleşimi artık **sekmeli çalışma alanı**; bkz. aşağıdaki bölüm. Eski "ana
  görünüm + Ayrıntılar akordiyonu" düzeni yok
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

### Donmuş girdiler tahmine katılmaz

`services/freshness.py` — bir makro girdi son **15 işlem gününde hiç değişmediyse**
tahmin anında eğitim ortalamasına çekilir (ölçekli uzayda sıfırlanır) ve yanıtta
`neutralized_features` olarak bildirilir. Karar sunucuda verilir; istemciye
bırakılsa çağıran atlayıp eski davranışa dönebilirdi.

**Neden:** `core_cpi_yoy` aylık yayımlandığı için 2026-08-03'ten beri sabitti
(20 işlem günü). Buna rağmen 30 günlük tahminin +%3,54'ünün **+3,02 puanını**
tek başına taşıyordu ve değeri 2,15, eğitim penceresinin **mutlak minimumu** —
model hiç görmediği bölgede ekstrapolasyon yapıyordu. Nötrleme sonrası aynı
girdiyle 30 günlük tahmin **+%3,58 -> +%0,70**.

Eşik ölçümle seçildi: 2026-08-31'de diğer makro girdilerin en uzun sabit kalma
süresi 4 gün, `core_cpi_yoy` 20 gün. 15 ikisini ayırır, normal yayın
gecikmelerini yakalamaz.

**Girdiyi eğitimden çıkarmak denendi ve geri alındı:** 18 girdiyle yeniden
eğitim ölçülen beceriyi yarıya indirdi (30g +%26,3 -> +%11,8; 14g tamamen
devre dışı) ve yönü **hiç değiştirmedi** (+%3,58 -> +%3,70) — ağ aynı rejimi
`vix_level` ve `yield_curve` üzerinden yeniden öğrendi. Nötrleme modeli
değiştirmez, yalnız bilgi taşımayan girdiye dayanmamasını sağlar.

**Ödünleşim:** servis edilen tahmin, karnede ölçülen tahminden farklılaşır;
İsabet Karnesi nötrlemesiz modeli ölçer. Arayüz hangi göstergenin hesaba
katılmadığını katkı kartında yazar.

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

## Teknik analiz paketi — tek kaynak backend (2026-09-06)

`backend/market-service/app/services/technical/` — destek/direnç, pivot, gösterge, trend,
momentum ve kırılım hesaplarının **tamamı** burada, saf Python (numpy yok). Arayüz yalnız
`GET /v1/market/xau/technical` yanıtını gösterir; frontend'de finansal formül kalmaz
(istisnalar aşağıda). İlke: her sayı deterministik, look-ahead'siz, oynaklığa (ATR) göre
normalize, testli ve `config_hash` ile izlenebilir.

```
candles.py    Candle/IntradayBar · normalize_daily/intraday (ret/klamp/tekrar sayaçları) ·
              aggregate (hafta Pzt / ay / çeyrek / yarıyıl) · previous_completed_period
indicators.py Wilder RSI/ATR/ADX, MACD(SMA tohumlu EMA), Stoch, Williams, CCI, ROC, MA tablosu
pivots.py     CLASSIC/FIBONACCI/CAMARILLA × günlük/haftalık/aylık (27 set) · build_ladder
swings.py     fraktal salınımlar (CONFIRMED / DEVELOPING)
levels.py     aday → ATR kümeleme → temas olayları → güç 0-100 → en yakın seçim
trend.py      trend.ts'in birebir portu (log-OLS, ddof=0 σ, düz seri guard'ı)
momentum_daily.py  günlük bileşik 0-100 (merkez 50), walk-forward delta/ivme
session.py    == eski momentum_service.py (git mv, matematik dokunulmadı)
breakout.py   iki taraflı kırılım gücü, olasılık değil
reference.py  referans fiyat (gün içi son kapanış, aynı enstrüman)
assemble.py   analyze() → TechnicalAnalysis · to_dict() → DTO
config.py     TechnicalConfig (tüm parametreler) · TA_ önekli env · config_hash
```

**Referans fiyat tek çerçevede.** Günlük seri (xaus, kaynağın kendi beyanıyla
`price_source: yahoo finance (GC=F)`) ile gün içi 5 dk barlar (Yahoo GC=F) aynı enstrüman;
referans = gün içi son kapanış, yoksa günlük kapanış (`reference.frame`). **Harem spot hiç
okunmaz** (`LIVE_QUOTE_NOT_USED`), yalnız başlıkta canlı kotasyondur. Ölçüldü: aynı merdiven
Harem'de (4431,6) P/S1, kapanışta (4476,6) R1/P veriyordu — çerçeve karıştırmak en yakın
seviyeyi değiştiriyor.

**Dönem tamamlanması iki kural:** takvim (hafta cumartesiden, ay bitince — ölçülmüş FE
kuralı) **ve** kapanış mumunun gerçekten gelmiş olması (cuma / ayın son iş günü) ya da
sonraki dönemden bir mum / 2 gün tolerans. Eksikse bir önceki döneme düşülür ve
`PERIOD_INCOMPLETE_FALLBACK` + `missing_bar_for` döner. Sebep: 2026-08-31'de kaynak 1 saat
503 verdi, 300 sn önbellekle cumartesi 4 günlük haftadan pivot üretmek mümkündü.

**Bölgeler (levels.py):** adaylar = salınım (1,0) + pivot (0,8; sabit yapısal küme: haftalık
klasik 7 + aylık P/S1/R1 + günlük P, görüntülenen setten bağımsız) + 20/60/250 gün uçları
(0,7) + 100 $ katları (0,2). Kümeleme toleransı `0,5·ATR`, tam-bağlantı tavanı `1,0·ATR`.
Temas: o günün ATR'siyle `±0,25·ATR_t`, ardışık temaslar tek olay, yeni olay için arada
`≥1 ATR` uzaklaşma. Sınıf: REJECTION / BREAK / NEUTRAL / PENDING (tepki penceresi as-of'u
aşıyorsa). Güç = 0,30 temas + 0,20 red + 0,20 tutunma (Laplace) + 0,15 konfluens + 0,10
yakınlık (90 gün yarı ömür) + 0,05 kaynak, son olay BREAK ise yarıya. **Matematiksel
garanti:** hiç test edilmemiş bir seviye en çok 28 alır, `min_strength` 30 → en yakın
destek/direnç en az bir kez test edilmiş olmak zorundadır. Referansın `±0,25·ATR` içindeki
bölge `testing`'dir ve **asla hedef değildir** (kullanıcı bildirimi kaynaklı ölçülmüş kural).

**Momentum iki blok:** `session` (5 dk, ölçülmüş eski servis, bit-identical fixture testi)
ve `momentum_daily` (günlük bileşik: hız 10g, sürüklenme 20g, RSI, MACD/ATR, ADX yönlü,
SMA50 uzaklığı; σ birimli; `score = 50 + 50·tanh(z/2)`; eksik bileşen atılır, ağırlık
yeniden dağıtılır). Fixture'da 59 · NEUTRAL · WEAK · CONFLICTING (10 günlük hız negatif,
SMA50'nin 2,7 ATR üstü pozitif). Skor dağılımı sd 20,5 (hedef ≈ 15) — `z_scale` kararı
doğrulama raporuna bırakıldı, uydurulmadı.

**Kırılım iki taraf, her zaman:** `√(min(1, beklenen hareket / uzaklık) · itme)`, itme =
0,6·seans + 0,4·günlük (seans yoksa ATR çerçevesi ve (0,1)), zıt yön ×0,25, hedef bölge
gücüne göre sönüm `1 − 0,5·güç/100`. Taban yok: momentum 0 → 0. Eski davranış bir
config'tir: `TA_BREAKOUT_WEIGHT_SESSION=1 TA_BREAKOUT_WEIGHT_DAILY=0 TA_BREAKOUT_LEVEL_DAMPING=0`
eski 0,469'u birebir üretir (test). NEUTRAL'de başlık yok ama iki taraf hesaplanır — BE/FE
test çelişkisi böyle çözüldü. `note: NOT_A_PROBABILITY`.

**Değişen sayılar (bilinçli):** referans Harem 4431,6 → GC=F 4476,6; varsayılan pivot
fib → **klasik** (haftalık); RSI/ATR/ADX Cutler/basit → **Wilder** (düz seride RSI 0 →
50; ADX artık DX'in Wilder ortalaması); kırılım etiketi MEDIUM → MODERATE. **Değişmeyen:**
seans bloğu (deep-equal), pivot değerleri (taban çizgisiyle 168/168 bitwise, canlı 56/56),
trend eğim/r²/σ (eski FE ile en kötü fark 3,8e-11), senaryo bölgeleri (model-service
`scenario_zones`, tarayıcı hesabıyla yarım sent içinde).

**Yolda bulunan tuzaklar:** `aggregate` DAILY dalı sırasız kopya döndürüyordu (pivot 2023
mumunu "dün" seçti; düzeltildi, test var). Dockerfile `python:3.12-slim` kalır: pinlenmiş
`pydantic 2.11.7` → `pydantic-core 2.33.2`'nin cp314 tekerleği yok, `2.12.5`'e yükseltmeden
3.14 imajı kurulmaz; venv 3.14 olduğu için kod 3.12 sözdiziminde tutulur. Trend
`last_bucket_forming` hafta için pazar bitişini bekler (pivot kuralından sıkı; bilgi alanı).

Fixture'lar `tests/fixtures/` (~200 KB, 2026-09-06 canlı yükleri ve eski FE değerleri);
testler `tests/test_technical_*.py`. Doğrulama raporu `docs/technical/VALIDATION.md`.

### Frontend tarafı (aynı gün)

- `services/api/technical.ts` → `parseTechnical`: `status` + `reference` zorunlu, her blok **ayrı**
  ayrıştırılır; bozuk/bilinmeyen enum o bloğu `null` yapar (bir kart gizlenir, sayfa değil).
  Seans bloğu değişmeden `parseMomentum`'dan geçer. Fixture `services/api/__fixtures__/technical.json`
  gerçek boru hattından üretildi (`assemble.to_dict`)
- `features/dashboard/useTechnical.ts`: 10 dk + görünürlük kadansı, pivot parametresi değişince
  300 ms debounce; `history/candles/lastClose/spot` `technical.daily`'den, `momentum` = seans bloğu.
  `data/model.json` 4643 tohumu ve `fetchXauHistory`/`fetchMomentum` kalktı; `/xau` ve `/xau/momentum`
  FE'den **hiç çağrılmaz** (ölçüldü: sayfa açılışında 5 API isteği)
- **Silinenler:** `domain/pivots.ts`, `domain/momentum/breakPotential.ts`, `domain/indicators/*`,
  `domain/chart/trend.ts`, `aggregate.ts`, `candles.ts`, `domain/tradeZones.ts` (+ testleri),
  `components/TickSparkline.tsx`, `model.json.resistance`. Kalan finansal hesap: `domain/loan.ts`,
  `ziynet.ts`, `quotes.ts` (Harem'e bağlı, kapsam dışı), `domain/model/*` (tahmin sunumu),
  `ZoneSection` `units` (kullanıcı girdisi hesap makinesi), `chart/geometry.ts` ve `scale.ts` (çizim)
- **Harem hiçbir hesaba girmez.** Tahmin isteğinin `price`'ı ve katkı kartının doları artık
  `technical.reference` (backend çerçevesi); önceden her Harem tick'i `values.price`'ı değiştiriyor,
  tahmin çapası ile bant birbirinden kayıyordu (adversaryal doğrulamada yüksek bulgu). Harem yalnız
  `PanelHeader` (canlı kotasyon) ve `ZiynetSection`'da
- **Güç betimleyicidir:** `docs/technical/VALIDATION.md` tarihsel testte STRONG > MODERATE
  sıralamasının tutmadığını gösterdi (tutma %44 < %51; en düşük tercil plasebonun altında). Arayüz
  bölge gücünü "N temas · son test <tarih> · çok/orta/az test edildi" olarak yazar (`TEST_INTENSITY`),
  "Güçlü seviye" demez. Kırılım kartında `NOT_A_PROBABILITY` notu her zaman görünür; günlük momentum
  "rejim" dilindedir (kuintil isabeti Q5 %72 ama Spearman ρ ≈ 0)
- İşlem bölgeleri model-service'ten (`/v1/predict.scenario_zones`, tahmin bandının geometrisi);
  alan yoksa "Senaryo bölgeleri sunucudan bekleniyor". **Dağıtım sırası:** model-service →
  market-service → web; her ara durum tanımlı (bölüm gizlenir, beyaz kart yok)
- Ölçüldü (yerel dist + yeni servisler, 375 px): `undefined/NaN` yok, konsol hatası 0, taşma 0,
  24 px altı kontrol 0, ray sırası referans → seviyeler → merdiven → momentum, Camarilla merdiveni
  9 satır. 12 px altı punto sayısı terminal katmanının bilinen regresyonu yüzünden arttı
  (`small`/`dt` kuralları; bkz. bilinen sorunlar) — yeni SCSS'te 12 px altı kural yok

## Gün içi momentum ve kırılım gücü

`backend/market-service/app/services/momentum_service.py` (saf modül, I/O yok) +
`frontend/src/features/momentum/MomentumSection.tsx`. Soru "fiyat çıkıyor mu iniyor mu"
değil: **mevcut hareket ilk seviyeyi kırmaya yetiyor mu.**

Girdi Yahoo'nun 5 günlük / 5 dakikalık mumları (`/v1/market/xau/intraday`), seviye
merdiveni ise **günlük OHLC** serisinden kurulur.

- **Sabit eşik yok.** Her gösterge o seansın mum getirisi standart sapması biriminde
  işaretli bir sayıya çevrilir; aynı 10 dolarlık hareket sakin seansta güçlü,
  çalkantılı seansta zayıf okunur. Kümeleme toleransı ve "seviye test ediliyor"
  marjı da aynı sigmadan türer
- Bileşen ağırlıkları eşik değil **editoryal tercih**: hız 0,25 · sürüklenme 0,20 ·
  ivme 0,20 · hacim 0,15 · RSI 0,10 · MACD 0,10. Eksik bileşenin ağırlığı kalanlara
  dağıtılır; hacim yoksa bu yanıtta `has_volume: false` olarak bildirilir
- **Güç** = sinyalin büyüklüğü × göstergelerin hemfikirliği, lojistikle 0-100'e
  sıkıştırılmış. **Yön** ayrı bir sorudur ve iki koşul ister: `|t| >= 1` **ve**
  fiyatın kendisinin rastgele yürüyüşten sapması; sağlanmazsa `NEUTRAL`
- **Sapma iki zaman ölçeğinden baskın olana bakar**: son bir saatlik *hız* ya da
  seans açılışından beri biriken *sürüklenme*. Önce yalnız hıza bakılıyordu ve gün
  boyu süren yavaş trendler görünmüyordu — ölçüldü (2026-09-01): son 1 saat
  z = −0,83 iken seansın tamamı −96 $ ve z = −1,65, bölüm "yön yok" diyordu.
  Sürüklenme n ile birikirken gürültü yalnız √n ile büyüdüğü için uzun pencere
  aynı eşikte daha güçlü bir testtir; **duyarlılık eşik gevşetilerek değil, tahmin
  edici güçlendirilerek** artırıldı. Aynı düzeltmeden sonra canlı veri
  `NEUTRAL · 6` yerine `DOWN · 60` verdi. Seansta bir pencereden az mum varsa
  sürüklenme hiç katılmaz
- **Kırılım gücü** iki şeyin geometrik ortalaması: seviyeye *ulaşmak* (beklenen
  hareket ÷ uzaklık, **1'de doyurulur**) ve onu kırmaya yetecek momentum

### Ölçümle düzeltilen üç tasarım hatası

1. **Gücü t istatistiğine bağlamak.** Bileşenler birlikte sıfıra çöktüğünde t yüksek
   kalıyor ve çalkantılı seans sakin seanstan güçlü okunuyordu (72 > 63). Büyüklük ×
   tutarlılığa geçince 3 < 51 oldu
2. **Yalnız t'ye bakıp yön vermek.** Sürüklenmesiz seride küçük ama tutarlı bileşenler
   t'yi 1'in üstüne çıkarıp sahte yön üretiyordu (hız 0,00 iken "UP"). `|hız| >= 1`
   ikinci kapı olarak eklendi
3. **Ham ulaşma oranı.** Fiyat seviyeye 0,2 sigma yakınken oran 88'e fırlıyor ve her şey
   `STRONG` çıkıyordu. Oran 1'de doyuruldu; seviyenin dibinde olmak onu kırmak değildir
4. **Yönü tek pencereye bağlamak.** Yalnız son bir saate bakılıyordu; gün boyu süren
   trend görünmüyordu (yukarıdaki −96 $ örneği). Seans sürüklenmesi hem bileşen hem
   yön kapısı olarak eklendi. Sahte yön üreten senaryolar korundu: sürüklenmesiz seri
   ve aynı sürüklenmenin çalkantılı hâli hâlâ `NEUTRAL`; güç sıralaması
   zayıf 48 < orta 77 < güçlü 93

### Seviye merdiveni üç çerçeveden gelir

İlk sürümde merdiven gün içi akışın **önceki seansından** türetiliyordu ve iki ayrı
kusur veriyordu (2026-09-01'de ölçüldü):

- Akışın önceki seansı **kırpık** geliyor: türetilen aralık 32,14 $, günlük mumun
  gerçek aralığı 56,0 $. Seviyeler olduğu gibi yanlıştı (S2 4413,47 yerine 4380,30)
- Fiyat merdivenin ucuna gelince bölüm **susuyordu**. Oysa bir sonraki anlamlı seviye
  vardı: haftalık S2 4314,50 ve 14 Ağustos salınım dibi 4315,00

Artık pivotlar **günlük mumdan** hesaplanır ve üç çerçeve tek merdivende birleşir:
günlük pivotlar, **haftalık** pivotlar (hafta cumartesi girince tamamlanmış sayılır —
pivot kartıyla aynı kural) ve son 40 günün **salınım tepe/dipleri** (iki komşusunu aşan
fraktal). Birbirine tolerans kadar yakın seviyeler tek seviyede toplanır ve kaç kaynağın
oraya işaret ettiği `sources` ile bildirilir — yukarıdaki 4314,75 iki kaynak taşır,
yani teyitlidir. Devam eden günün mumu merdivene **girmez**.

### Üzerinde durulan seviye hedef değildir

Kullanıcı bildirdi: gösterilen seviye çoktan kırılmıştı. Fiyat bir seviyenin gürültü
kadar yakınındaysa o seviye "kırılacak" değil **test ediliyor** demektir. Bu yüzden
`support`/`resistance`/`breakout` bu marjın içindeki seviyeleri **atlar** ve hedef bir
sonraki gerçek seviye olur; temas edilen seviye ayrıca `touching` alanında döner ve
arayüzde ayrı bir not olarak yazılır.

### Arayüz

- Bölüm "Ayrıntılar" içinde `Collapsible`; panel özelliği `altin-momentum-gucu`,
  çapa `feature-momentum`. `altin-destek-direnc` rehberi (başlığı zaten "Destek, Direnç
  ve Momentum") buraya bağlanır
- **Momentum grafiğe çizilmez** (denendi, kalabalıklaştı, geri alındı). 5 Eylül'den beri
  özet, Genel bakış sekmesinin sağ rayında `MomentumSummary` (güç ölçeği + yön + trend +
  `DataTimestamp`, 15 dk sonra "gecikmeli"); tam bölüm Teknik analiz sekmesinde pivot
  kartının yanında. Yön rengi: yukarı yeşil, aşağı kırmızı, yönsüz nötr
- **Seviyeler tek kaynaktan: panelin pivot merdiveni.** Hem özet kart hem Ayrıntılar'daki
  momentum bölümü `pivotLadder`'ı ve kartların fiyatını kullanır; momentum servisi yalnız
  **yön, güç, trend ve seansın beklenen hareketini** sağlar. Önce ikisi servisin kendi
  merdivenini gösteriyordu ve aynı ekranda iki farklı "ilk direnç" çıkıyordu
  (ölçüldü: kart $4.398 ↔ momentum hedefi $4.436)
- **Kırılım iki taraf, her zaman** (2026-09-06): `breakout.up` / `breakout.down` backend'den;
  `headline` yalnız seans yönü UP/DOWN iken. Eski `domain/momentum/breakPotential.ts` silindi
- **Hesap oransaldır.** Momentum gün içi vadeliden (Yahoo `GC=F`), kartlar spottan (Harem)
  besleniyor; aradaki ~%1 seviye farkı ancak oranda sadeleşir. Testle sabit: fiyat
  çerçevesi %0,95 ötelenince skor 10 ondalığa kadar değişmiyor. Formül servisinkiyle
  aynı — doyurulmuş ulaşma × güç, geometrik ortalama
- Servisin `support`/`resistance`/`touching`/`breakout`/`ladder` alanları API'de duruyor
  ama **arayüz onları kullanmaz**; istemci (`services/api/momentum.ts`) yalnız momentum
  büyüklüklerini çevirir
- Etiket sözlüğü tek kaynakta: `content/momentum.ts` (`DIRECTION`, `TREND`, `BREAK`, `MOMENTUM_DAILY`)
  + `content/technical.ts` / `indicators.ts` / `trend.ts` (enum → Türkçe metin); bileşenlerde
  satır içi enum metni yok, `content.test.ts` fixture'daki her enum değerinin sözlükte olduğunu tarar
- Yanıt `services/api/momentum.ts` → `parseMomentum` ile doğrulanır; bozuk şema `null`
  döner ve bölüm hiç görünmez. Kullanılmayan seviye alanları bozuk gelse bölüm yine ayakta

## Trend grafiği kartı

`frontend/src/features/trend/` — tahmin grafiğinin yanına ikinci bir kart. Sorusu farklı:
tahmin grafiği modelin **beklentisini**, bu kart geçmişin **genel yönünü** gösterir.

- 2026-09-06'dan beri seriler ve regresyon backend'den gelir (`technical.trend.ranges`; `trend.py`
  birebir port). Toplama kuralı aynı: Kova anahtarları takvimle uyumlu — hafta pazartesiye
  çekilir, çeyrek ve yarıyıl takvim sınırlarından
- Aralıklar `features/trend/ranges.ts` içinde: **Günlük** (90 mum, varsayılan) ·
  Haftalık (104) · Aylık (60) · 3 Aylık (24) · 6 Aylık (12). Günlük mum, diğerleri çizgi
- Trend çizgisi noktaları birleştirmez: **log fiyat üzerinde en küçük kareler**
  (backend `technical/trend.py`). Log uzayında sabit yüzde büyüme düz bir doğrudur, o yüzden
  eğim "dönem başına yüzde kaç" olarak okunur ve serinin başı ile sonu eşit ağırlık taşır
- Kart beş sayı verir: yön, eğim (dönem başına), **gerçekleşen** değişim, kanaldaki
  konum ve uyum (r²)
- **Regresyon kanalı**: artıkların ±1σ ve ±2σ bandı. Sigma log uzayında hesaplandığı
  için bant fiyat ekseninde **çarpımsal** açılır — %8'lik sapma yüksek fiyatta daha çok
  dolar eder ve bant öyle görünmelidir. Kanal yönle renklendirilmez; bir iddia değil,
  trend etrafındaki tipik sapmadır ve r²'yi görünür kılar
- **Kanalın dışına çıkmak dönüş sinyali sayılmaz.** Denendi ve ölçüldü: 250 günlük
  regresyona göre fiyat trendin 1σ altındayken sonraki 30 günün ortalama getirisi
  +%1,81, koşulsuz ortalama ise +%3,12 — yani sapma *aleyhte* çıktı. Üstelik elde
  üst üste binmeyen yalnız **33 adet** 30 günlük pencere var; bu farklar o örneklemde
  gürültüdür. Kanal bu yüzden yalnız betimleyici olarak sunulur, sinyal olarak değil
- Tasarım dili paylaşılan sınıflardan gelir (`chart-block`, `chart-head`, `segmented`,
  `chart-wrap`, `market-snapshot`); ölçüldü: kabuk, başlık, özet kartı, eksen yazısı,
  ızgara ve pasif düğme hesaplanan değerleri mevcut kartla birebir aynı

### Ölçümle düzeltilen iki şey

1. **Yön eşiği adım başına eğime bakıyordu.** Kova uzunluğu değişince anlamı kayıyordu:
   günlük mumda %0,1/gün yılda %28 (çok kaba), 6 aylık kovada hiçbir şey (çok ince).
   Ölçüldü: 90 günde **−%6,37** olan gerçek seri "Yatay" görünüyordu. Karar artık
   **dönem boyu toplam değişimden** verilir (eşik %1), her kovada aynı anlamı taşır
2. **Kartta trend çizgisinin uçları yazıyordu.** 60 aylık seride ham değişim %148,14 iken
   trend uçları %202,91 — okuyucu bunu fiyat değişimi sanardı. Kart artık **gerçekleşen**
   değişimi gösterir; trendin kendi uçları grafikte zaten çizili

Sabit seride kayan nokta yüzünden `syy` sıfır yerine ~1e-31 çıkıyor ve r² **1 yerine 0**
oluyordu; log uzayında 1e-10'un altındaki yayılım düz kabul edilerek düzeltildi
(`trend.test.ts` bunu doğrular). Toplam 42 test.

### SEO tarafı

Kartın panel karşılığı `altin-trend-grafigi` ve **içerik taşıdığı için** sitemap'e girer
(kural: `sections` yoksa `noindex`). Ön render'da 783 özgün kelime, render sonrası
`PanelIntro` aynı metni gösterir — ikisi tutarlı. `ons-altin-yil-sonu-tahmini` rehberi
buraya bağlandı: o makale uzun vadeli tahminin neden verilmediğini anlatıyor, bu kart
ise uzun vadenin fiilen ne yaptığını gösteriyor.

Panel sayfasında `h1` (panel başlığı) ile kartın `h2`'si aynı metni taşır ama aralarında
~4.100 piksel var; okuyucu ikisini birlikte görmez, ikincisi canlı aracın etiketi olarak
çalışır.

## Sekmeli çalışma alanı ("terminal" yerleşimi, 2026-09-05, `033e9eb`)

`DashboardPage` beş sekmeli bir çalışma alanı: **01 Genel bakış** (tahmin özeti + grafik,
sağda "ray": ilk destek/direnç, `PriceLadder` merdiveni, `MomentumSummary`; altta
`OverviewInsights` = en büyük üç katkı) · **02 Teknik analiz** (trend, pivot + momentum yan
yana, göstergeler) · **03 Model** (katkı, karne; vade seçici) · **04 Piyasalar** (ziynet,
bülten) · **05 Senaryolar** (TL getirisi, işlem bölgeleri; vade seçici).

- Sekme `?view=` sorgu parametresinde (`setSearchParams`, kaydırma sıfırlanmaz); rol
  `tablist/tab/tabpanel`, ok tuşları ve Home/End çalışır. Panel içeriği **ziyaret
  edildiğinde** bağlanır (`visited` kümesi), sonra `hidden` ile saklanır — bir sekmeye
  dönmek yeniden yüklemez
- `/panel/:slug` ve `#feature-*` çapaları `ANCHOR_VIEW` ile doğru sekmeye çözülür
  (`feature-pivot` → technical, `feature-karne` → model…). `useFeatureFocus`'ta
  `NAVBAR_OFFSET` 84 → **132** (yapışkan menü 60 + sekme çubuğu 52) ve görünmeyen düğüm
  (`getClientRects().length === 0`) için kaydırma atlanır
- `Collapsible` bir `AnalysisPresentation` bağlamı okur: çalışma alanında `'section'`
  değerini alır ve **düz bölüm** olarak render olur (başlık + özet + gövde, akordiyon yok);
  bağlam dışında eski akordiyon davranışı durur
- `PanelHeader` artık **piyasa özeti**: `h1` "Ons altın" + `XAU / USD` kodu, büyük fiyat,
  günlük kapanış hareketi (geçmiş serinin son iki kapanışından), dört göstergeli `dl`
  (USD/TRY, gram, geniş dolar 5g, reel faiz 5g), `DataTimestamp` ve Yenile. Spinner'lar
  buradan kalktı; boş değer "—" ile gösterilir. `demoted` ile `h1` → `h2`
- `PanelIntro` (panel sayfalarının anlatısı) artık çalışma alanının **altında**, `SeoContent`'ten
  önce basılır; ön render sırası aynı değil (bkz. bilinen sorunlar)
- `SeoContent` editoryal: 3 öne çıkan rehber (`featuredIds`) + `details` içinde kategori
  bazlı tam dizin (`GUIDES_BY_CATEGORY`); eski 37 konu hapı listesi yok
- Stil: `_terminal.scss` + `_terminal-tables/-analysis/-charts/-editorial.scss` (972 satır)
  `index.scss`'in **en sonunda** `@use` edilir; yani eski modüllerin üstüne yazılan bir
  **override katmanı**. Mobile-first: 12 `min-width` sorgusu (380/420/560/600/640/760/
  900/1020/1024/1080) + `prefers-reduced-motion`. `_tokens.scss` yeniden yazıldı: 74 token,
  yeni `--space-1…16`, `--radius-sm/md/lg`, `--font-mono`, `--page-width: 1440px`,
  `--motion-fast`; iki tema aynı anahtarları taşır, otomatik sistem geçişi hâlâ yok; terminal dosyalarında sabit hex yok
- Ölçüldü (canlı, 375 px, 2026-09-06): 89 kontrolün **0'ı** 24 px altında, taşma 0, konsol
  hatası 0, sekmeler ve `?view=` çalışıyor. Punto regresyonu için bilinen sorunlara bak

## Makale verisi ana pakette değil

`seo-articles.json` 313,6 KB ham / 84,4 KB gzip ve tamamı giriş paketine giriyordu —
anasayfaya gelen herkes 37 makalenin **tam metnini** indiriyordu. Oysa anasayfa, rehber
dizini, footer ve gezinme yalnız başlık ve özet gösteriyor.

- `scripts/build-article-index.mjs` gövdesiz bir indeks üretir (**15,8 KB ham / 4,5 KB
  gzip**) → `src/data/articles-index.json`. Dosya **depoya işlenir** ki `vite dev` ön adım
  gerektirmesin; `build` betikleri onu her seferinde yeniden üretir
- `content/articles.ts` yalnız indeksi statik içe aktarır. Gövde iki yoldan gelir:
  **(1) organik iniş** — ön render edilen sayfa gövdeyi `<script type="application/json"
  id="makale-verisi">` olarak taşır ve `useState` başlangıç değeri olarak **eşzamanlı**
  okunur; **(2) uygulama içi gezinme** — tam veri bir kez tembel yüklenir
- Ölçülen sonuç: giriş paketi **219 → 140,3 KB gzip (−%36)**; makale gövdeleri ayrı
  `seo-articles-*.js` chunk'ına taşındı

**Gömme neden şart:** React hidrasyonda ön render edilen metni atar. Veri gelene kadar
yükleniyor gösterilseydi organik inişte içerik bir an kaybolurdu — sayfanın tek işi
okunmak olduğu için bu kabul edilemezdi. Ölçüldü: 6 saniye boyunca 250 ms aralıkla
örneklendi, bölüm sayısı **10'da sabit kaldı**, yükleniyor durumu hiç görünmedi ve
makale chunk'ı **hiç istenmedi**. Gömülü veri sayfaya 3,3 KB gzip ekliyor, ek istek yok.

`</script>` enjeksiyonuna karşı `<` karakteri `\u003c` olarak kaçırılır.

**Ayrışma riski ve testi:** indeks üretilmiş ama işlenmiş bir dosya; kaynak değişip
yeniden üretilmezse ikisi ayrışır. `content/articles.test.ts` bunu yakalar: aynı kimlikler
aynı sırada, özet alanları birebir, indekste gövde alanı yok, indeks kaynağın onda
birinden küçük. Bu testlerin koşması için `vite.config.ts` içindeki vitest `include`
listesine `src/content/**` eklendi.

**Yolda görülen:** panelde bazı iç bağlantılar react-router `<Link>` değil düz `<a href>`
(`ZiynetSection` gibi). Bunlar tam sayfa yeniden yüklemesi yapıyor; çalışıyor ama SPA
gezinmesinden yavaş.

## Rota bazlı kod bölme (2026-09-04)

Makale verisini ayırdıktan sonra giriş paketi hâlâ 145 KB gzip'ti ve rehber
sayfasına organik gelen okuyucu panelin tamamını (grafik, socket.io, 12 bölüm)
indiriyordu. Sayfa türleri artık `app/App.tsx` içinde `React.lazy` ile ayrı parça:
`pages/DashboardRoute.tsx` (sağlayıcı + panel, socket.io burada), `ArticlePage`,
`GuideHubPage`, `PanelHubPage`, `SitePageView`.

| sayfa | önce | sonra |
|---|---|---|
| rehber makalesi | 145 KB | **~99 KB** (giriş 96 + makale 1,3 + footer 1,1) |
| panel / anasayfa | 145 KB | 144 KB (giriş 96 + panel 48) |

Giriş paketindeki 96 KB React 19 + react-router + ortak kabuk (SiteNav, LegalModal,
makale indeksi); panele ait hiçbir şey kalmadı (imza dizeleriyle doğrulandı).

- **Organik inişte metin kaybolmaz.** Ön render `#root` içinde ve React render'ı
  onu siler; parça gelene kadar `Suspense` yedeği olarak **ön render edilmiş HTML'in
  kendisi** gösterilir (`app/prerender.ts`, modül render'dan önce yakalar). Yalnız
  iniş yolunda ve tek sefer: uygulama içi gezinmede başka sayfanın metni yedek
  olarak görünmesin diye sınır çözülünce `prerenderConsumed` çağrılır.
  Ölçüldü: 4 sn boyunca 250 ms'de bir örneklendi, kelime sayısı 1380–1399, h1 sabit,
  spinner hiç görünmedi
- **Ek gidiş-dönüş yok.** `vite.config.ts` manifest üretir; `generate-seo-pages.mjs`
  her ön render edilmiş sayfaya kendi rota parçasının `modulepreload` bağlantısını
  basar (giriş paketinin zaten yüklediği ortak parçalar atlanır). Manifestte parça
  yoksa build **hata verir**, sessizce preload'suz kalmaz
- Doğrulandı: makale sayfası yalnız `index + ArticlePage + SiteFooter` istiyor,
  panel parçası hiç inmiyor; anasayfa `DashboardRoute` alıyor, makale parçasını
  almıyor; uygulama içi gezinme ve geri tuşu çalışıyor, konsol hatası yok

## SEO

- 37 rehber makalesi (`data/seo-articles.json`), 12 panel özelliği (`data/panel-features.json`),
  4 kurumsal sayfa (`data/site-pages.json`: hakkımızda, yazar, iletişim, gizlilik)
- `scripts/generate-seo-pages.mjs` build sonrası: 37 rehber + `/rehber` dizini + 5 dizine açık panel
  sayfası + `/panel` dizini + 4 kurumsal sayfa + ön render edilmiş anasayfa +
  **49 URL'lik sitemap**
- **Güven sayfaları (E-E-A-T).** YMYL kategorisinde Google'ın aradığı sinyaller sitede hiç
  yoktu. Dört sayfa `SitePageView` şablonuyla render edilir, ön render edilir ve her ön
  render edilmiş footer'dan (`LEGAL` sabiti) linklenir. Article şemasının `author`'ı artık
  `/yazar`'a bakar. `SitePageView` başlığa site adını bir kez ekler — `useDocumentMeta`
  zaten ekliyordu, iki kez markalanıyordu
- **Makale derinliği.** 30 makalenin **tamamı** ~210 kelimeden 1101–1468 kelimeye çıkarıldı;
  her biri 7-8 bölüm ve 8 SSS taşır, hepsinde bir tablo, 25'inde ayrıca liste var.
  Ortalama 1218 kelime / 631 benzersiz kelime, şablon payı %21. Makaleler modelin
  **kendi ölçülmüş sayılarını** kaynak olarak kullanır (MAE, yön, beceri, ağırlık) —
  rakiplerin kopyalayamayacağı tek içerik bu
- **Makaleler arası tekrar yok.** Aynı SSS sorusu birden fazla makalede geçince sayfalar
  aynı snippet için birbiriyle yarışıyordu; 8 soru ve 10 bölüm başlığı ayrıştırıldı.
  30 tablo başlığının hepsi benzersiz
- **Makale şemasında tablo ve liste var** (`SeoTable`, `SeoList` — `content/types.ts`).
  Sayısal içerik düz paragrafta kayboluyordu. Tablo `.article-table-wrap` içinde ve
  `overflow-x:auto`; mobilde tablo kendi içinde kayar, sayfa taşmaz (ölçüldü: 375 px
  ekranda gövde taşması 0, 336 px'lik tablo 293 px'lik saran divde)
- **Ön render ile React işaretlemesi ayrışmıştı.** `generate-seo-pages.mjs` tabloyu saran
  div ve sınıflar olmadan basıyordu: ön render edilen tablo hem stilsiz kalıyor hem de
  yatay taşma koruması taşımıyordu. Google'ın gördüğü HTML bu olduğu için üretici
  `ArticlePage` ile birebir eşitlendi (`article-table-wrap`, `article-table`, `article-list`)

### 2026-09-01'de eklenen sekiz makale

Anahtar kelime araştırması sonucu iki boşluk kapatıldı; ikisi de yeni kategori:

- **Gram Altın ve Kur** (4 makale) — site ons/USD ekseninde kuruluydu, Türkçe arama talebi
  gram/TL ekseninde. Makaleler gram hareketini **ons katkısı** ve **kur katkısı** olarak
  ayırır. Kritik sınır: model yalnız XAU/USD tahmin eder, **USD/TRY tahmini yok**; bu yüzden
  gram tarafında fiyat hedefi değil senaryo tablosu verilir
- **Hesaplama ve İşçilik** (4 makale) — bilezik ve ziynet işçilik hesabı. Panelin canlı
  ölçtüğü değerlere dayanır (gram %0,1, ziynet %1–2) ve `ZIYNET_SPECS` milyem tablosunu
  kullanır; rakiplerin statik örnek hesaplarından ayrıştığı yer burası

Kalite kapıları makineyle denetlendi: 854–1211 kelime, 7–8 bölüm, 8 SSS, 6 madde, özet
130–160 karakter, her makalede tablo. Site genelinde **SSS soruları, bölüm başlıkları
ve tablo başlıklarının tamamı benzersiz** — aynı snippet için yarışan sayfa yok.

### Search Console ölçümü planı düzeltti (2026-09-01)

İlk plan SERP kompozisyonuna dayanıyordu ve sıralaması **yanlış çıktı**. Mülkün ilk
verisi (13–29 Ağustos, 16 gün, 44 tıklama, 1.161 gösterim, 132 sorgu) şunu gösterdi:

| tema | tıklama | gösterim | ort. konum |
|---|---|---|---|
| destek-direnç / teknik | **19** | 153 | 13,5 |
| yorum / analiz talebi | 3 | 124 | 25,0 |
| çeyrek / gram çevrimi | 0 | 113 | **80,9** |
| FED / faiz | 0 | 60 | 24,4 |
| **gram altın / kur** | 0 | **0** | — |

- Planın 1. kümesi (gram/kur) **hiç gösterim almadı**; 5. kümesi (teknik) sorgu bazlı
  tıklamaların **%73'ünü** getirdi. 132 sorgunun tamamı ons eksenli — Google siteyi
  "ons altın teknik analiz" olarak sınıflandırmış
- Çeyrek/gram çevrimi alanında site **80. sırada**; alan kuyumcu ve hesap makinesi
  siteleriyle doymuş. Bu küme donduruldu
- `ons-altin-yorum` makalesi bu ölçümden çıktı: `ons altın yorum` sorgusu 60 gösterim
  ve **konum 11,5** ile ilk sayfanın hemen altında, sıfır tıklamayla duruyordu ve sitede
  "yorum" kelimesini hedefleyen tek bir sayfa yoktu
- Trafiğin **%76'sı mobil**, mobil TO masaüstünün iki katı (%4,21 / %2,48)

### İndeksleme durumu (Coverage raporu, 28 Ağustos 2026)

Sitenin **48 URL'sinin 31'i dizinde, 17'si değil** ve sayı **22 Ağustos'tan beri sabit** —
indeksleme yayla yapmış. Dizine eklenmeyenlerin dökümü:

| sebep | sayfa |
|---|---|
| Bulunamadı (404) | 1 |
| Keşfedildi, henüz taranmadı | 10 |
| Tarandı, dizine eklenmedi | 6 |

- **404'ün kaynağı bulundu:** `paxg-usdt-nedir`. PAXG kaynağı projeden çıkarılırken makale
  de silinmiş ama URL Google'ın hafızasında kalmıştı. `frontend/nginx.conf` içine konu
  olarak en yakın sayfaya **301** eklendi (`fiziki-altin-mi-dijital-altin-mi`); 404
  bırakmak birikmiş sinyali çöpe atardı. Kural `location =` ile yazıldı, tam eşleşme
  `^~ /rehber/` kuralından önce değerlendirilir
- "Keşfedildi ama taranmadı" 10 sayfa, yeni sitelerde tarama bütçesinin dar olmasından
  gelir; "tarandı ama eklenmedi" 6 sayfa ise kalite/benzerlik sinyalidir
- **Sonuç:** 48 URL'nin %35'i dizinde değilken sayfa eklemek, hareket etmeyen bir kuyruğa
  eklemek demek

### Dizine eklenmeyenlerin tamamı panel sayfaları (drilldown, 28 Ağustos)

URL dökümü çekildiğinde tek bir örüntü çıktı: **16 sayfanın 11'i `/panel/*`** ve o tarihte
sitede **12 panel URL'i vardı (hub + 10 slug + hub'ın kendisi)** — yani panel bölümünün
**tamamı** dizin dışı. Kalan 5: `/hakkimizda`, `/iletisim` ve üç rehber
(`bir-ons-altin-kac-gram`, `gram-altin-fiyati-nasil-belirlenir`, `merkez-bankalari-altin-alimi`).

**Sebebi ölçüldü — ince ve şablon içerik:**

| | panel sayfası | rehber sayfası |
|---|---|---|
| gövde metni | ~350 kelime | ~1.300–1.500 kelime |
| metin satırı | 47 | — |
| **başka panelle ortak satır** | **42** | — |
| **sayfaya özgü kelime** | **121** | 1.478 |

Yani her panel sayfasının **%89'u diğer on paneille birebir aynı**; özgün kısmı başlık,
özet ve tek bir giriş paragrafından ibaret. Google dördünü tarayıp indekslememiş,
yedisini taramaya bile değer görmemiş. Bu, "Tarandı - dizine eklenmedi" durumunun
ders kitabı tanımı.

**Üç gram sayfası tek sayfada birleştirildi.** `bir-ons-altin-kac-gram` ve
`gram-altin-fiyati-nasil-belirlenir` aynı konuyu (formül, ayar/milyem, kuyumcu farkı)
üçüncü kez anlatıyordu; Google dizinde yalnız `ons-gram-altin-hesaplama`'yı tutmuştu.
Başka yerde olmayan içerik — troy ons ile normal ons ayrımı ve külçe ölçüleri — hayatta
kalan sayfaya bir bölüm olarak taşındı, kümenin en çok aranan sorusu (`1 ons altın kaç
gram?`) SSS'ye eklendi ve iki URL `nginx.conf` içinde **301** ile oraya yönlendirildi.
`ZiynetSection` içindeki iç link de doğrudan hedefe çevrildi; iç bağlantının
yönlendirmeden geçmesi gereksiz.

### Asıl sebep ince içerik değil, yinelenen içerikti

Ön render'a metin eklemek işe yaramazdı. `app/App.tsx` içinde `/panel/:slug`
**`<Dashboard focus={slug}/>`** render eder; yani React hidrasyonunda ön render edilen
metin tamamen atılır ve 11 URL de aynı panoyu gösterir. Deneyle ölçüldü
(`/panel/altin-tl-getirisi`, JS sonrası): `.seo-prerender` **yok**, h1
**"Canlı Ons Altın Tahmin ve Senaryo Analiz Paneli"** — yani panelin değil panonun
başlığı. Anasayfa `/` aynı panonun kanonik hâli ve dizinde; Google birini seçip
kalanını elemiş.

**Çözüm — `PanelIntro`:** panel özelliği isteğe bağlı `sections` taşır. Taşıyorsa
`DashboardPage` panonun **üstüne** o panele ait blok basar (kendi `h1`'i, özeti,
bölümleri) ve `PanelHeader` başlığını `h2`'ye indirir — sayfada tek `h1` kalır.
Aynı bölümler ön render'da da basılır, böylece ön render ile render **aynı** şeyi
gösterir. Taşımıyorsa sayfa `noindex,follow` alır ve `scripts/site-routes.mjs`
onu sitemap'e koymaz. Yani **dizine girmenin koşulu içerik taşımaktır**; ayrı bir
bayrak yok, unutulamaz.

- İçerik yazılan paneller ölçümün kazanan dediği kümeden: `altin-pivot-seviyeleri`,
  `altin-momentum-gucu`, `ons-altin-tahmini`, `altin-teknik-gostergeler` ve
  `altin-trend-grafigi`
- Ön render'daki özgün kelime **121 → 594-786**; sitemap 57 → **50 URL**, panel 12 → 4
- `routes.test.ts` değişti: sitemap artık uygulama rotalarının **alt kümesi**.
  Ters yön hâlâ hata (sitemap'te olup rotada olmayan yol 404 verir) ve ayrı bir test
  sitemap'teki panel listesinin tam olarak `sections` taşıyanlar olduğunu doğrular
- **Ölçüm tuzağı:** `.panel-intro` kendisi bir `<section>`. `intro.querySelector('section p')`
  ata birleştiricisi yüzünden lede'yi yakalıyor; bölüm paragrafını ölçmek için
  `:scope > section p` gerekir. İlk ölçümde punto yanlış okundu
- Atlama bağlantısı metnin **başında**: okuyucu panoyu kullanmaya geliyor, 1500 piksel
  metin kaydırmak zorunda kalmasın
- `enflasyon-fed-altin` **yerinde yeniden yazıldı** (id ve URL korundu, birikmiş konum
  kaybolmasın diye). Sorguların tamamı "nasıl etkiler" kalıbında geliyordu; başlık ve
  anahtar kelime o dile çevrildi. Asıl boşluk **tutanaklardı**: `fed tutanakları altını
  nasıl etkiler` sorgusu konum **9,8**'de duruyordu ama sayfada tutanaklar hiç geçmiyordu.
  Sayfa artık FED döngüsünü dört ayrı olay olarak ele alıyor (beklenti · karar metni ·
  basın toplantısı · tutanaklar). Komşu makalelerle iş bölümü: onlar **mekanizmayı**
  (reel faiz, dolar endeksi, enflasyon), bu sayfa **olayı** anlatır
- **Uyarı:** 8 yeni gram/işçilik makalesi bu ölçümden sonra yayımlandı, indekslenmediler.
  Veri onların potansiyelini yanlışlamaz; ölçüm 3–4 hafta sonra tekrarlanmalı
- Çözümleyici repoda: `tools/gsc_analiz.py`. GSC dışa aktarımını (ZIP ya da CSV) okuyup
  sorguları yukarıdaki temalara göre gruplar, fırsat ve eşleşmeyen sorguları listeler.
  Bağımlılığı yok; `python3 tools/gsc_analiz.py --self-test` ile 15 sınaması var
- **İki tuzak sınamayla sabitlendi:** GSC Türkçe dışa aktarımı konum sütununu `Pozisyon`
  adıyla verir (`Ortalama konum` değil) ve yerel ayara göre sayı biçimi değişir —
  `1.240` binlik ayraçtır, `8,4` ondalıktır. İlk sürüm `1.240`'ı 1,24 okuyordu ve
  1.240 gösterimlik bir sorgu **1 gösterim** görünüyordu
- Zamanlanmış hatırlatıcı: `~/.claude/scheduled-tasks/onsaltinanaliz-gsc-olcum/`,
  28 Eylül 2026'da bir kez çalışır ve ölçümü yukarıdaki temelle karşılaştırır
- Meta açıklamaları 130–160 karakter aralığında (bazıları 75 karakterdi)
- **Her rehber, canlı karşılığı olan panel bölümüne bağlanır.** `seo-articles.json` içindeki
  `panel` alanı hedef slug'ı verir; hem `ArticlePage` hem `generate-seo-pages.mjs` bir CTA
  basar. Ön render edilen sürümde bulunması şart — Google'ın indekslediği ve JavaScript
  çalışmadan görülen HTML o. Öncesinde makalelerden panele **tek bir link bile yoktu**
- nginx `absolute_redirect off` + `/panel` ve `/rehber` için ayrı `location =` blokları
  (protokol düşüren 301 sorunu bu yüzden çözüldü)
- `/panel/<slug>` ile gelindiğinde ilgili bölüm açılır, yerleşim durulunca tek yumuşak
  kaydırma yapılır ve kısa süre vurgulanır (`useFeatureFocus`)

## Hız sınırı ve dokunma hedefleri (2026-09-03)

- **API hız sınırı konteyner nginx'inde** (`frontend/nginx.conf`), Python bağımlılığı yok.
  `limit_req_zone` / `limit_conn_zone` dosyanın en üstünde — `conf.d/*.conf` `http`
  bağlamına dahil edildiği için geçerli (sunucuda `nginx -t` ile doğrulandı). Yalnız
  `/(market-service|model-service)` proxy bloğuna uygulanır; statik varlıklar sınırsız.
  Değerler: **10 istek/sn, burst 40 nodelay, 20 eşzamanlı bağlantı**, aşımda **429**.
  Cömert seçildi: trafiğin %76'sı mobil ve Türkiye'de mobil kullanıcıların çoğu operatör
  NAT'ı arkasında — tek IP'yi çok kullanıcı paylaşır, dar sınır önce gerçek kullanıcıyı
  keser. Ölçüldü: 6 istekli sayfa açılışı ve 10 statik istek tamamen geçer; 80 istekli
  ardışık selin 31'i 429 alır
- **Konteyner gerçek istemci IP'sini `X-Real-IP`'den okur** (`set_real_ip_from
  172.16.0.0/12` + `real_ip_header X-Real-IP`). İlk dağıtımda ölçüldü: konteyner her
  isteği docker ağ geçidi `172.18.0.1` olarak görüyordu, yani sınır kişi başına değil
  **site geneli** uygulanıyordu. Host nginx zaten `X-Real-IP` gönderiyor ve konteynere
  yalnız o ulaşıyor (`127.0.0.1:8080`); `X-Forwarded-For` değil `X-Real-IP` seçildi
  çünkü tek değer taşır, zincirle sahtelenemez. Doğrulama: A 80 istekte 33 kez 429
  yerken B aynı anda 200 aldı. Canlı: 80 istek 20 paralel → 27 tanesi 429
- **Ardışık curl ile sınır tetiklenmez**: TLS üzerinden istek başına ~0,2 sn, yani
  ~5 istek/sn. Canlıda sınamak için paralel gönder (`xargs -P 20`)
- **Punto tabanı 12 px** (2026-09-04). Mobilde ~1.000 metin düğümünün ~350'si 9–11,5 px
  arasındaydı (eyebrow 9, olasılık bandı 11). SCSS'te 12'nin altındaki 122 `font-size`
  kuralı 12'ye çekildi; grafik SVG metinleri (eksen, seviye etiketi, CANLI) kapsam dışı,
  onlar piksel alanıyla sınırlı. `_base.scss` içinde `small{font-size:12px}` tabanı var:
  tarayıcı varsayılanı `smaller` ile 10 px'e düşüyordu. Ölçüldü: 375 px'de 12 px altı
  **0**, taşma 0, kırpılan metin 0
- **Çıplak `header` seçicisi tuzağı:** `_legacy-responsive.scss` mobilde `header
  { flex-direction:column }` diyordu ve bu, ziynet kart başlığı gibi **her** `header`
  öğesine sızıyordu (başlık ortalanmış sütuna dönüyordu). Kural `.app > header` ile
  sınırlandı. `_base.scss`'teki `header{display:flex…}` de çıplak; kart başlıkları kendi
  düzenini yazdığı için şimdilik zararsız, yeni bir `header` eklerken hatırla
- **Marka görselleri `alt=""` taşır ve bu doğru:** üst menü ve altbilgideki logo
  hemen yanında "Ons Altın Analiz" metniyle duruyor, bağlantının kendisi adlandırılmış.
  Alt metin eklemek ekran okuyucuya adı iki kez okuturdu; "alt'sız görsel" sayımı boş
  alt'ı eksik saymıştı
- **Dokunma hedefleri WCAG 2.2 SC 2.5.8 (AA, 24×24) uyumlu.** 375 px'de 123 kontrolün
  **18'i** 24 px'in altındaydı; neredeyse tamamı footer bağlantıları (11 px punto,
  17 px yükseklik) ve "Yasal uyarının tamamı" düğmesi (113×18). Punto korundu,
  yükseklik `min-height:24px` + `inline-flex` ile verildi; negatif yatay marj
  metni sütun hizasında tutar (ölçüldü: metin solu = başlık solu). Satır ritmi
  değişmedi: masaüstünde `gap` 9→2, mobilde 11→4, ikisinde de eski toplam
  (26 / 28 px). **Sonuç 18 → 0**, gövde taşması 0

## Dağıtım

- `docker-compose.yml`: api-gateway, market-service, model-service, web. Yalnız `web`
  dışarı açık (`127.0.0.1:8080`), TLS host nginx'te (`deploy/nginx/onsaltinanaliz.com.conf`)
- **Sıkıştırma konteyner nginx'inde** (`frontend/nginx.conf`), host'ta değil. Host'ta
  `gzip on;` vardı ama `gzip_types` yorumdaydı; nginx varsayılanı yalnız `text/html`
  olduğu için JS ve CSS **ham gidiyordu** (ölçüldü: JS 759,8 KB, CSS 72,4 KB,
  ikisi de `Content-Encoding`'siz). Düzeltmenin burada olmasının sebebi: sunucudaki
  `/etc/nginx/sites-available/onsaltinanaliz.com` **repoya bağlı değil**
  (`deploy/nginx/` yalnız referans kopya), yani host'ta yapılan düzeltme sunucu
  yeniden kurulunca kaybolurdu. Konteyner yapılandırması ise sürümleniyor.
  Host zaten sıkıştırılmış yanıtı olduğu gibi geçirir; nginx `Content-Encoding`
  taşıyan bir yanıtı yeniden sıkıştırmaz. Ölçülen kazanç **839,5 KB → 241,0 KB (%71)**
- **Önbellek politikası üç kademeli** (aynı dosyada): varsayılan `no-cache` (HTML,
  sitemap, robots ve API — her zaman doğrula), `/assets/` için
  `max-age=31536000, immutable` (dosya adı içerik hash'i taşır, içerik değişirse ad da
  değişir), hash'siz görseller için bir hafta. **Tuzak:** nginx'te bir location'da
  `add_header` tanımlanırsa üst bloktan gelenleri **ezer**; bu yüzden her kademe kendi
  başlığını eksiksiz yazar. `^~ /assets/` regex kuralından önce değerlendirildiği için
  oradaki `.svg` dosyaları bir haftalık kurala düşmez
- **Güvenlik başlıkları konteyner nginx'inde** (`frontend/nginx-security.conf`, 2026-09-04):
  CSP, `X-Frame-Options: DENY`, `Permissions-Policy`. Dosya `add_header` tanımlayan
  **her** blokta `include` edilir — nginx'te bir location kendi `add_header`'ını
  yazınca üst bloktakiler ezilir; doğrulama gerçek dist ile altı yol türünde
  (HTML, makale, /assets, görsel, /health, API) başlığın tam bir kez çıktığını ölçtü.
  CSP: `script-src 'self'` + `index.html`'deki satır içi tema betiğinin sha256
  hash'i; `style-src 'unsafe-inline'` (React nitelik stilleri); `connect-src`
  Harem soketi; `frame-ancestors 'none'`. **Betik değişirse hash değişmeli**:
  `src/app/csp.test.ts` hash'i betikten yeniden hesaplayıp CSP'de arar, soket
  adresini `services/config.ts`'ten okuyup `connect-src`'de arar. HSTS, nosniff ve
  referrer-policy host nginx'te kalır; burada tekrarlanırsa başlık iki kez gider
- **api-gateway zaman aşımı yol bazlı** (`router_service.timeout_for`): varsayılan
  **90 sn** (`UPSTREAM_TIMEOUT_SECONDS`), `/v1/training*` için **300 sn**
  (`UPSTREAM_SLOW_*`), bağlantı kurma 5 sn. Eskiden her istek 300 sn'ydi; takılan
  üst servis gateway işçisini beş dakika tutuyordu. 90, market-service'in
  birincil + yedek fiyat kaynağını (30 + 30 sn) kapsar
- Serving yolu değişiklikleri **iki kademe doğrulanır**: sunucuda compose ağına bağlı
  geçici konteynerde `nginx -t`, ardından çalışan `web`'in gerçek dist içeriği
  kopyalanıp ayrı bir konteynere bağlanarak istek atılır. Canlıya hiç dokunulmaz
- Model imajı proje kökünden build edilir (CSV'yi kopyalayabilmek için)
- **Log rotasyonu ve kaynak sınırları compose'da** (2026-09-04). Loglar `json-file`
  sınırsızdı (api-gateway birkaç günde 2,6 MB); artık her konteyner 3 × 10 MB tutar.
  Bellek sınırları ölçülen tepenin en az 4 katı: gateway/market 256M, model 512M
  (eğitim tepesi 121 MB), web 64M; CPU tavanları 1 / 1 / 1,5 / 0,5, süreç 256.
  Dar sınır güvenlik değil kesinti üretir (OOM → yeniden başlatma). **Tuzak:**
  `pids_limit` ile `deploy.resources.limits` aynı anda yazılamaz, compose ikisini
  aynı alana çözümler; süreç sınırı `limits.pids` olarak verilir. Doğrulama
  sunucuda `docker compose -f <geçici> --project-directory /opt/... config` ile
- Sunucu ve deploy adımları: [[altin-model-deployment]] (hafıza)

## Test

```
frontend: 19 dosya, 191 test (vitest: domain + lib + app + services + content + features)
backend : market-service 368 (teknik paket 14 dosya) · model-service 148 · api-gateway 7 (pytest)
tsc --noEmit temiz
```

`src/app/csp.test.ts` dosyaları Vite `?raw` içe aktarımıyla okur ve hash'i Web Crypto ile
alır; `node:fs`/`node:crypto` kullanılamaz çünkü projede Node tipleri yok ve `tsc` kırılır
(vitest yine geçer — iki denetim farklı şeyi görür).

Vitest bu Node sürümünde `.bin/vitest` sarmalayıcısıyla çalışmıyor:
`node node_modules/vitest/vitest.mjs run` kullan.

## Bilinen sorunlar ve temizlik borcu

0. **5 Eylül sonrası ölçülen regresyonlar (2026-09-06, canlı 375 px):**
   - **Punto tabanı bozuldu.** 4 Eylül'de 12 px altı 0'a indirilmişti; terminal katmanı
     **96 kural** ile 10–11 px'i geri getirdi. Ölçüm: Genel bakış 131, Teknik 189, Model 109,
     Piyasalar 166, Senaryolar 79 metin düğümü 12 px altında (`.section-kicker`, `small`,
     `dt`, `.layer-state`, `.guide-groups h3` 10 px…). Düzeltme yeri `_terminal*.scss`
   - **Ön render ile render ayrıştı.** `generate-seo-pages.mjs` `homeFallback` hâlâ
     `h1` "Canlı Ons Altın Tahmin ve Senaryo Analiz Paneli" ve "Panel bölümleri" listesi
     basıyor; React'in bastığı `h1` **"Ons altın"**. Google ilkini görüyor, kullanıcı
     ikincisini. Panel sayfalarında `PanelIntro` ön render'da üstte, render'da altta
   - Şampiyon modelde **7 günlük ufuk kapalı** (ağırlık 0,00) ve yeni akışta model
     kendiliğinden yenilenmeyecek; 7g'yi geri getirmek operatör kararı ve terfi kapısı
     mevcut veriyle kapalı
   - `reports/model-audit-20260905/` (9,7 MB, `results.json` 60 bin satır) git geçmişinde;
     pack 45 MB. Yeni denetim çıktıları repoya işlenmemeli
   - `_base.scss`'teki çıplak `header{display:flex…}` hâlâ duruyor (bkz. çıplak `header` tuzağı)
   - Panel bazı iç bağlantılarda hâlâ düz `<a href>` kullanıyor (tam sayfa yükleme)
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
backend/market-service/.venv/bin/python -m pytest backend/market-service/tests
backend/api-gateway/.venv/bin/python -m pytest backend/api-gateway/tests
# çevrimdışı model denetimi (ağ yok, canlı yazma yok, terfi yok):
backend/model-service/.venv/bin/python backend/model-service/scripts/run_model_audit.py --output /tmp/audit
backend/model-service/.venv/bin/python backend/model-service/scripts/export_frontend_fallback.py
cd frontend && node node_modules/vitest/vitest.mjs run && npx tsc --noEmit
docker compose up -d --build
```
