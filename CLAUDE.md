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
| market | `GET /v1/market/xau` | xaus.com günlük OHLC, 300 sn önbellek, **yedek kaynaklı** |
| market | `GET /v1/market/fred?id=` | FRED CSV (curl_cffi ile), 900 sn önbellek, son 800 gün |
| market | `GET /v1/market/news` | Google News RSS, 10 başlık |
| market | `GET /v1/market/xau/intraday` | Yahoo 5 günlük 5 dakikalık mumlar, 60 sn önbellek |
| market | `GET /v1/market/xau/momentum` | gün içi momentum, seviye merdiveni ve kırılım gücü |
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
- Otomatik job veri setini saatlik tazeler; en az `RETRAIN_EVERY_NEW_ROWS` (varsayılan 5)
  yeni satır oluşunca yeniden eğitir ve `RETRAIN_MINIMUM_ROWS`'u (300) uygular
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
- **Yazı tipi bilinçli sistem yığını; web font yüklenmez.** Önceden `Inter` bildiriliyor
  ama hiçbir yerde yüklenmiyordu (ölçüldü: `document.fonts.size = 0`). Sonuç, Inter'in
  kurulu olduğu makinede bir yüz, Android ve Windows'ta başka bir yüzdü — marka yazı tipi
  kullanıcıların çoğuna hiç ulaşmıyordu (trafiğin %76'sı mobil, çoğu Android). Sistem
  yığını seçildi çünkü sitenin birinci sorunu yük ve Inter marka karakteri katmayan bir
  varsayılan; maliyeti ödeyip özgünlük kazanılmıyordu. Karakter istenirse doğru yer gövde
  değil, **başlıklar için ayrı bir display yüz**. Sıra platformun kendi arayüz yüzünü
  önceler ve hepsi Türkçe diyakritikleri karşılar. Doğrulandı: sıfır font ağ isteği,
  375 ve 780 px'te HTML kırpılması 0, gövde taşması 0
- **İki tema var, varsayılan aydınlık.** Palet `styles/_tokens.scss` içinde **56 token**
  olarak tanımlı; aydınlık palet `:root`'ta, koyu palet `:root[data-theme="dark"]`'ta ve
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
- **Spinner nerede dönüyor**: panel başlığındaki ONS ve USD/TL kartları (akış canlı
  değilken durum noktasının yerini alır), yenile düğmesi, tahmin kartları, grafik vade
  kartı, ziynet bölümü, bülten haberleri, TL getirisi, işlem bölgeleri ve ayrıntı
  bölümlerinin yer tutucusu. Model servisi çevrimdışıysa ayrıntı yer tutucusu spinner
  yerine durumu yazar — sonsuza kadar dönen gösterge yanıltıcı olurdu
- **Kontrast ölçülüyor.** Her iki temada tüm görünür metinler WCAG AA'ya göre denetlendi
  (anasayfa 418, rehber 132, kurumsal 59 öge): sıfır hata. Aydınlık temada `--text-dim`,
  `--gold`, `--teal`, `--blue` bu denetim sonucu koyulaştırıldı
- **`.skip-link` özgüllük hatası düzeltildi**: `.site-nav a` rengi eziyordu, atlama bağlantısı
  altın zemin üzerinde okunmuyordu (koyu temada kontrast 1,13)
- **Bölüm sırası DOM sırasıdır.** `_panel-shell.scss` içinde App.tsx monolitinden kalma
  `.content > .chart-block { order:2 }` / `.cards { order:3 }` gibi kurallar vardı; `.content`
  grid olduğu için bunlar DOM sırasını eziyor, **grafik ve tahmin kartları "Ayrıntılar"ın
  altına düşüyordu**. Kurallar kaldırıldı — sıra artık yalnız `DashboardPage`'ten gelir.
  Sıra değişikliği doğrulanırken DOM sırası yetmez, ekrandaki dikey konum ölçülmelidir
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
- **Momentum grafiğe çizilmez.** Hedef ve test edilen seviye grafikte mavi çizgi-nokta
  deseniyle işaretlenmişti; pivot merdiveni zaten çizili olduğu için grafik kalabalıklaştı
  ve geri alındı. Momentum artık grafiğin **altındaki özet kartlarda**, "Yukarıda ilk
  direnç"in hemen yanında duruyor (`.snapshot-card.momentum-card`, dizgi 4 → 5 sütun;
  mobilde 2 sütunda direnç kartıyla aynı satıra düşüyor). Kenarlık yönü kodlar:
  yukarı yeşil, aşağı kırmızı, yönsüz nötr — mavi kullanılamaz, "Şu anki fiyat" kartı almış
- **Seviyeler tek kaynaktan: panelin pivot merdiveni.** Hem özet kart hem Ayrıntılar'daki
  momentum bölümü `pivotLadder`'ı ve kartların fiyatını kullanır; momentum servisi yalnız
  **yön, güç, trend ve seansın beklenen hareketini** sağlar. Önce ikisi servisin kendi
  merdivenini gösteriyordu ve aynı ekranda iki farklı "ilk direnç" çıkıyordu
  (ölçüldü: kart $4.398 ↔ momentum hedefi $4.436)
- **Hedef yönden çıkar**: yukarı yönlüyse *ilk direnç*, aşağı yönlüyse *ilk destek*;
  `NEUTRAL` iken hedef verilmez — yön belirsizken "şu seviyeyi kırar" demek uydurma olur.
  Seçim ve hesap `domain/momentum/breakPotential.ts` içinde, iki bileşen de oradan okur
- **Hesap oransaldır.** Momentum gün içi vadeliden (Yahoo `GC=F`), kartlar spottan (Harem)
  besleniyor; aradaki ~%1 seviye farkı ancak oranda sadeleşir. Testle sabit: fiyat
  çerçevesi %0,95 ötelenince skor 10 ondalığa kadar değişmiyor. Formül servisinkiyle
  aynı — doyurulmuş ulaşma × güç, geometrik ortalama
- Servisin `support`/`resistance`/`touching`/`breakout`/`ladder` alanları API'de duruyor
  ama **arayüz onları kullanmaz**; istemci (`services/api/momentum.ts`) yalnız momentum
  büyüklüklerini çevirir
- Etiket sözlüğü tek kaynakta: `content/momentum.ts` (`DIRECTION`, `TREND`, `BREAK`,
  `BREAK_SHORT`); hem momentum bölümü hem özet kart oradan okur
- Yanıt `services/api/momentum.ts` → `parseMomentum` ile doğrulanır; bozuk şema `null`
  döner ve bölüm hiç görünmez. Kullanılmayan seviye alanları bozuk gelse bölüm yine ayakta

## Trend grafiği kartı

`frontend/src/features/trend/` — tahmin grafiğinin yanına ikinci bir kart. Sorusu farklı:
tahmin grafiği modelin **beklentisini**, bu kart geçmişin **genel yönünü** gösterir.

- Yeni uç yok: panelin zaten çektiği günlük OHLC serisi seçilen aralığa toplanır
  (`domain/chart/aggregate.ts`). Kova anahtarları takvimle uyumlu — hafta pazartesiye
  çekilir, çeyrek ve yarıyıl takvim sınırlarından
- Aralıklar `features/trend/ranges.ts` içinde: **Günlük** (90 mum, varsayılan) ·
  Haftalık (104) · Aylık (60) · 3 Aylık (24) · 6 Aylık (12). Günlük mum, diğerleri çizgi
- Trend çizgisi noktaları birleştirmez: **log fiyat üzerinde en küçük kareler**
  (`domain/chart/trend.ts`). Log uzayında sabit yüzde büyüme düz bir doğrudur, o yüzden
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
frontend: 18 dosya, 145 test (vitest: domain + lib + app/routes + services)
backend : model-service 46 test, market-service 48 test (pytest)
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
