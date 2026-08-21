# CLAUDE.md — Proje İndeksi

Ons altın (PAXG/USDT referanslı) fiyat tahmin platformu. React SPA + 3 FastAPI mikroservisi + SQLite.
Prod: https://onsaltinanaliz.com (Docker Compose + host Nginx, sunucu 5.75.148.203).

## Repo haritası

```
frontend/                 React 19 + TS + SCSS + Vite (katmanlı: lib/domain/services/features/pages/app)
backend/api-gateway/      Tek dışa açık giriş, saf reverse-proxy (port 8000)
backend/market-service/   Binance / FRED / Google News veri kaynağı (port 8001)
backend/model-service/    MLP tahmin + otomatik toplama & yeniden eğitim (port 8002)
backend/data/             gold_platform_<env>.sqlite3 (üç servis ortak dosya, tablolar servis bazlı ayrık)
deploy/nginx/             Sunucudaki host Nginx (TLS terminasyonu + 127.0.0.1:8080'e proxy)
docker-compose.yml        Prod orkestrasyonu
start-profile.sh          Lokal: 3 servis + vite (profil: localhost|development|production)
```
Kök `api-gateway/`, `market-service/`, `model-service/` klasörleri yalnızca eski `.venv` kalıntısıdır; kod `backend/` altındadır.

## Mimari akış

`Tarayıcı → (nginx :443) → web konteyneri nginx :80 → api-gateway :8000 → market|model-service`

- Gateway URL'i **servis adıyla başlamak zorunda**: `/market-service/...`, `/model-service/...`
  (`app/services/router_service.py`). Gateway öneki soyar, kalanı upstream'e iletir.
- Market ve model servisleri lokalde yalnız `127.0.0.1` dinler; Docker'da ise ağ izolasyonuyla korunur.
- Hata standardizasyonu: `GatewayException` → `{timestamp,status,code,message,path,service,trace_id}` + `X-Trace-Id` (`app/exceptions/`).
- Her istek `gateway_request_logs` tablosuna yazılır (`app/database.py`).

## Backend uçları

| Uç | Servis | Not |
|---|---|---|
| `GET /health`, `GET /gateway/routes` | api-gateway | proxy'den önce tanımlı |
| `GET /v1/market/binance` | market | PAXGUSDT 1d, 260 mum, TTL 60 sn |
| `GET /v1/market/spot` | market | 24hr ticker, TTL 5 sn |
| `GET /v1/market/fred?id=` | market | CSV; `curl_cffi` ile `impersonate="chrome"` (FRED bot engeli), TTL 900 sn |
| `GET /v1/market/news` | market | Google News RSS, TTL 600 sn |
| `POST /v1/predict` | model | `{price, features}` → mean/error/prices |
| `POST /v1/snapshots` | model | günlük gözlem kaydı + tahmin hedefleri açar, vadesi dolanları kapatır |
| `GET /v1/learning/metrics` | model | horizon bazlı MAE/RMSE/yön/bant |
| `POST /v1/training/run` | model | MLPRegressor yeniden eğitimi |
| `GET /v1/learning/job` | model | otomatik job durumu |

## Model / öğrenme döngüsü

- **Etiket kaynağı daima Binance PAXGUSDT.** Harem ONS yalnız gösterim; fark `observations.basis_usd`'de tutulur, eğitimde kullanılmaz.
- Horizon: 7 / 30 / 90 / 180 gün. 31 özellik (teknik + FRED makro).
- Soğuk başlangıç: `model-service/data/initial_model.json` (5 ağlı ensemble, saf NumPy ileri besleme, `residual80 × BAND_SCALE=0.81` bant).
- Eğitilmiş model: `MLPRegressor(28,12)`, `%80` eğitim / kalan doğrulama, `residual70` bant. Artefakt `MODEL_DIR/<version>.joblib` + `active.json` işaretçisi, `model_versions` tablosuna kayıt.
- Otomatik job (`automatic_learning_service.py`): saatlik (`COLLECTION_INTERVAL_SECONDS=3600`), veriyi **gateway üzerinden** çeker, snapshot yazar, `AUTO_TRAIN` ve `rows ≥ 80` + `yeni satır ≥ 20` koşulunda eğitir.
- Şema: `observations` (PK trade_date) · `prediction_runs` (UNIQUE base_date) · `prediction_targets` (run+horizon) · `model_versions`.

## Frontend

2026-08-20'de tek dosyalık `src/App.tsx` (880 satır) katmanlı mimariye taşındı.

```
src/lib/          saf yardımcılar (math, format, series, meta) — hiçbir şeye bağımlı değil
src/domain/       iş kuralları; React ve ağ yok, model artefaktı parametre olarak alınır
    model/        network · predict · features · impacts · types
    market/       goldFeatures (mumlardan) · macroFeatures (FRED serilerinden)
    indicators/ · pivots · supportResistance · scorecard · loan · tradeZones
src/services/     ağ katmanı; config · http · api/{market,model} · realtime/{binance,harem}
src/content/      metin ve veri tek kaynağı: articles · panel · parameters · site · types
src/features/     ekran bölümleri (dashboard, chart, ziynet, scorecard, indicators,
                  pivots, impact, loan, bulletin, zones, parameters, forecast, guides)
src/components/   paylaşılan parçalar: SiteNav · SiteFooter · Collapsible · LegalModal · TickSparkline
src/pages/        DashboardPage · ArticlePage · GuideHubPage · PanelHubPage
src/app/          App (React Router) · routes · ScrollToTop · useDocumentMeta
src/styles/       32 SCSS modülü + index.scss
```

Bağımlılık yönü tek yönlüdür: `app → pages → features → services/content → domain → lib`.
Domain katmanı `model.json`'ı **import etmez**; artefakt `src/data/artifact.ts` üzerinden
parametre olarak geçirilir, bu sayede küçük sahte modellerle test edilebilir.

- **Durum yönetimi:** `features/dashboard/DashboardContext.tsx`. Dört hook'tan oluşur —
  `useMarketData` (REST + iki soket), `usePanelSettings` (yalnız görünüm tercihleri),
  `useForecastModel` (parametre formu + tahmin), `useDailySnapshot`. Türetilmiş her değer
  (impacts, pivotLadder, tech, scorecard, loan, zones) burada `useMemo` ile hesaplanır ve
  bölümler prop almadan `useDashboard()` ile okur.
- **Rotalar:** React Router. `src/app/routes.ts` ile `scripts/site-routes.mjs` aynı JSON'lardan
  aynı yolları üretir; `routes.test.ts` ikisinin birebir eşit olduğunu doğrular — sayfa eklenip
  sitemap'e (ya da tersi) yazılmaması artık testte patlar. Site içi bağlantılar `<Link>`;
  `#` çıpaları ve `/sitemap.xml` düz `<a>` kaldı.
- **Meta:** SPA gezinmesinde başlık/kanonik `useDocumentMeta` ile sayfaya göre güncellenir.
  Öncesinde tek dosya olduğu için makaleden anasayfaya dönüldüğünde makale başlığı kalıyordu.
- **Test:** 84 test, 13 dosya (`vitest`, node ortamı). Kapsam yalnız `domain/`, `lib/` ve
  rota tablosu — kullanıcı kararıyla bileşen testi yazılmadı.
  Çalıştırma: `node node_modules/vitest/vitest.mjs run` (`.bin/vitest` sarmalayıcısı bu Node
  sürümünde çalışmıyor).
- `API_BASE` şablonu: `.env.production` → `{origin}` (aynı origin, nginx proxy), `.env.localhost` → `http://{host}:8000`.
- Canlı veri: Binance WS (`wss://stream.binance.com:9443/ws/paxgusdt@ticker`) + Harem socket.io (`wss://hrmsocketonly.haremaltin.com`, ONS ve USDTRY) — bunlar tarayıcıdan **doğrudan**, gateway'siz. Soketler yalnız panel rotalarında açılır; rehber sayfaları `DashboardProvider`'ı mount etmez.
- Tahmin: `POST /model-service/v1/predict` (700 ms debounce); istek düşerse `src/data/model.json` ile tarayıcı içi ensemble fallback.
- Günde bir kez `POST /model-service/v1/snapshots` (Europe/Istanbul günü, `useDailySnapshot` içinde `pending:` işaretiyle tekilleştirme).
- SEO: `scripts/generate-seo-pages.mjs` build sonrası `src/data/seo-articles.json` ve
  `panel-features.json`'dan `dist/rehber/<id>/`, `dist/panel/<slug>/`, iki dizin sayfası,
  ön render edilmiş anasayfa ve 44 URL'lik sitemap üretir.
### Grafik (`features/chart`)

2026-08-20'de ölçek ve etkileşim elden geçirildi.

- **viewBox = ölçülen piksel kutusu.** `useElementSize` saran `div`'i ölçer, SVG `viewBox`'ı
  bire bir aynı yazılır; ölçek tam 1 olur. Öncesinde viewBox sabitti (1600×650 / 420×620):
  masaüstünde ayrılan yüksekliğin **113px'i (%18)**, 651–720px arası genişliklerde
  **219px (%33)** boş kalıyordu ve SVG içindeki 10px'lik yazı ekranda **7,6px** basılıyordu.
  `ResizeObserver` tek dayanak değildir — `<svg>` üzerinde hiç tetiklenmediği ortamlar var
  (ölçüldü); her render sonrası `useLayoutEffect` ölçümü ve `resize`/`orientationchange`
  dinleyicileri de var.
- **Tek kırılma noktası.** Dar yerleşim ölçülen genişlikten türer (`COMPACT_WIDTH = 650`);
  `usePanelSettings`'teki `mobile` bayrağı kaldırıldı. Eskiden JS 720px'te, CSS 650px'te
  ayrıldığı için arada kalan genişlikler bozuk çiziliyordu.
- **Dikey ölçek** `domain/chart/scale.ts` içindedir (saf, testli). Belirsizlik bandı
  çekirdek serilerin payını `MIN_CORE_SHARE` (0,5) altına düşürmeyecek kadar dahil edilir;
  taşan uç kırpılır ve grafikte "bant uçları kırpıldı" notu çıkar. Tam değerler ipucunda
  ve günlük tabloda durmaya devam eder.
- **Zaman ekseni** artık tarih gösterir (`pickTimeTicks` + `dropNear`); ufuk çıpaları
  geniş ekranda "13.09 · 1 Ay" biçiminde etiketlenir. Öncesinde eksende hiç tarih yoktu.
- **Hareketler** `useChartGestures`: sürükleyerek kaydırma, iki parmakla yakınlaştırma,
  Ctrl'süz tekerlek zoom'u, dokun-sabitle imleç (dokunmatikte parmak kalkınca ipucu
  kayboluyordu). `touch-action: pan-y` — dikey sayfa kaydırma serbest kalır.
  Sabitlenen ipucu parmağın altında kalmasın diye çizim alanının üstüne yerleşir.
- Mobilde "Sıfırla" düğmesi geri geldi (yalnız simge); y etiketleri çizim alanının içine
  alınarak sol kenar boşluğu 34px'ten 10px'e indi.
- `model.latestDate` seçili geçmiş aralığında değilse karşılaştırma katmanı çizilemez;
  efsanedeki düğme artık pasifleşir ve nedenini `title` ile söyler.
- **İpucu köken katmanından ayrıldı.** Projeksiyon, efsane düğmesi kapalıyken de hesaplanır;
  geçmiş bir güne gelince "gerçekleşen / o günkü tahmin / sapma" görünür. Öncesinde imleç
  noktaları köken projeksiyonu ile aynı `i` değerini paylaşıyor, eşitlikte projeksiyon
  kazanıyordu; bir geçmiş günün gerçek kapanışı ipucunda hiç görünmüyordu.
- **Erişilebilirlik:** SVG odaklanabilir (`tabIndex`), `<title>`/`<desc>` ile özetlenir ve
  `aria-describedby` ile günlük tabloya bağlıdır. Ok tuşları gün gün gezer (Shift ile hafta,
  PageUp/Down ay, Home/End uç, Esc kapatır); seçilen nokta `aria-live` bölgesinden okunur.
  Nokta görünür pencerenin dışındaysa pencere ona kayar.
- **Günlük tablo** varsayılan olarak kapalı; açıldığında yalnız vadesi dolan günleri listeler,
  "N günün tamamı" düğmesiyle tümü gelir. Başlık `origin-key` rengiyle işaretlidir — tablo
  canlı tahmini değil, grafikteki kesikli mavi katmanı listeler. Mobilde bölüm yüksekliği
  1423px'ten 1030px'e indi.
- Ölü kontrol ve stiller temizlendi: her ekranda `display:none` olan `.wide-toggle` düğmesi
  ve hiç kullanılmayan `.origin-band` kuralı kaldırıldı.

- SCSS eski `styles.scss` + `chart.scss` sırasını **birebir koruyacak şekilde** bölündü;
  derlenmiş CSS bölme öncesiyle karakterine kadar aynı (yorumlar hariç doğrulandı).
  `styles/index.scss` içindeki `@use` sırası bozulursa özgüllük çakışmaları değişir.

## Deployment

- `docker-compose.yml`: 4 servis, `gold-data` + `gold-models` volume'ları, healthcheck zinciri (`web → api-gateway → market/model`).
- Yalnız `web` port yayınlar: `127.0.0.1:8080:80`. Dışarıya açılış host Nginx üzerinden.
- `frontend/nginx.conf` SPA'yı sunar ve `/market-service|/model-service` yollarını konteyner içi `api-gateway:8000`'e proxy'ler; `/rehber/` statik SEO sayfaları.
- `deploy/nginx/onsaltinanaliz.com.conf` host tarafında: 80→443, `www`→apex, Let's Encrypt (`/var/www/certbot`), HSTS, `127.0.0.1:8080`'e proxy.
- Prod deploy: sunucuda `docker compose up -d --build`.

### Sunucu (2026-08-18 doğrulandı)

- Host `ali-dogan-services` @ `5.75.148.203`, repo `/opt/altin-model-react`, compose projesi `altin-model-react`.
- 4 konteyner de `Up (healthy)`; dışa açık tek port `127.0.0.1:8080->80` (`web`).
- Sistem Nginx (`www-data`, `/etc/nginx/conf.d/*.conf` ile site conf'u dahil ediliyor).
- Kaynak: disk 38G / %10 dolu, RAM 3.8G (~2.9G available), **swap yok**.
- Canlı durum: `environment=production`, `model_version=initial-2026-08-14`, otomatik job saatlik çalışıyor ve `last_error=null`.
  `prediction_days=4`, `pending_targets=16` — 180 günlük horizon nedeniyle ilk yeniden eğitim (80 tam satır) için aylar gerekiyor.

## Komutlar

```bash
./start-profile.sh localhost          # 3 servis + vite dev
pnpm --dir frontend typecheck
pnpm --dir frontend test              # 84 test (domain + lib + rota tablosu)
pnpm --dir frontend build:production
backend/<servis>/.venv/bin/python -m pytest backend/<servis>/tests
docker compose up -d --build
```

## Model durumu

Üretimde **eski model** çalışıyor (`initial-2026-08-14`, `frontend/src/data/model.json`
üzerinden 5 ağlı ensemble). 2026-08-18'de yazılan yeni hat (sürüklenme çapası +
purge'lü CV + beceri ağırlıklı düzeltme) kullanıcı kararıyla geri alındı;
`model-rework-20260818` dalında commit `31f446f` olarak duruyor.
Geri getirmek için: `git cherry-pick 31f446f`.

Eski model hakkında ölçülen ve hâlâ geçerli olan bulgular (2026-08-18):

- **Yön hatası:** 10Y reel faiz (`DFII10`) −3sd→+3sd taramasında 180g tahmini
  +14.6% → +27.5% *artıyor*. Ekonomik olarak ters. `DTWEXBGS`, `VIXCLS` ve TÜFE
  serilerinin işaretleri de ters.
- **Sabit terim baskın:** 31 özellik aynı anda ±1sd oynatıldığında (2000 senaryo)
  180g çıktısı [+4.5%, +42.5%] — **hiçbir senaryoda düşüş yok**. 30g'de parametre
  kaynaklı sapma sd=1.28p, modelin kendi bandı ±6.89p.
- **Azami ayı senaryosu** → 180g **+46.2%**, bandın alt ucu +22.6%.
- **Metrikler yanıltıcı:** eğitim penceresinde (2022-07→2026-08, PAXG +154%)
  "her zaman YUKARI de" kuralı 180g'de %88.6 isabetli; modelin raporladığı
  `direction` 0.693 — naif kuraldan kötü. 30g'deki 0.872 örtüşen pencere yanlılığı.
- **Kök neden:** 180g için 1447 örtüşen satır ≈ 8 bağımsız pencere; 31 özellik
  bu veriden öğrenilemez.

Model **fiyat değil getiri** üretiyor; `price` 31 özelliğin içinde değil. Fiyat
seviyesi canlı Binance spot'undan gelir, parametreler yalnız yüzde değişimi kaydırır.

`trainer.py` içindeki `import json` eksikliği 2026-08-18'de düzeltildi (geri alma
kapsamı dışında tutuldu): hata `joblib.dump` sonrası patlıyor, `active.json` ve
`model_versions` kaydı yazılmıyor, bu da sonsuz saatlik yeniden eğitim döngüsü
yaratıyordu.

## SEO içerik sistemi (2026-08-18'de yeniden kuruldu)

- İçerik kaynağı: `frontend/src/data/seo-articles.json` (31 makale). Hem `src/content/articles.ts` hem
  `scripts/generate-seo-pages.mjs` aynı dosyadan okur; üretici eskiden `App.tsx`'i string
  indeksiyle parse edip `Function()` ile eval ediyordu, artık düz JSON okuyor.
- Makale şeması: `id, keyword, title, seoTitle, updated, summary, intro, sections[], points[], faq[]`.
  `title` H1'dir, `seoTitle` `<title>` etiketi içindir (60 karakter sınırı bunun üzerinden tutulur).
- `npm run build` = `vite build` + üretici. Üretici `dist/index.html`, `dist/rehber/*/index.html`
  ve `dist/sitemap.xml` dosyalarını yazar. `public/sitemap.xml` kaldırıldı (bayat kopyaydı).
- İç linkleme dönen pencereyle yapılır (`relatedOf`): her makale kendinden sonraki 5 makaleye
  link verir, böylece her sayfa tam 5 inbound link alır. Eski `slice(0,5)` her zaman ilk beşi
  seçtiği için 21 sayfanın 15'i hiç iç link almıyordu.
- Anasayfa artık ön render edilir; `<div id="root">` içine H1, tanıtım metni ve 31 rehbere
  giden link listesi yazılır. Öncesinde tarayıcıya 23 kelime ve sıfır başlık gidiyordu.

Ölçülen durum (öncesi → sonrası): anasayfa 23 → 798 kelime, 0 → 31 iç link, başlıksız → H1+H2;
rehber sayfaları 21 → 31 adet, ortalama 200 → 419 kelime, gövde içi ara başlık 0 → 6 H2 + 3 H3;
iç link almayan sayfa 15 → 0; şema `Article/BreadcrumbList` → `Article/FAQPage/BreadcrumbList/Person`;
`dateModified` build tarihi → içeriğin kendi `updated` alanı; makale sayfalarındaki yanlış
`WebApplication` şeması kaldırıldı.

## Navigasyon

- `SiteNav` (`src/components/SiteNav.tsx`) `<details>` yerine kontrollü React state kullanır: dışarı tıklama,
  Escape ve link tıklaması menüyü kapatır; `aria-expanded`/`aria-current` doğru işaretlenir.
- Rehberler açılır listesi `category` alanına göre gruplanır ve arama kutusuyla filtrelenir.
- **Mobil panel `createPortal` ile `document.body`'ye taşınır.** `.site-nav` üzerindeki
  `backdrop-filter`, `position:fixed` alt öğeler için içeren blok yarattığından panel
  navbar'ın içine hapsolup 1 piksele çöküyordu. Portal edildiği için `.site-nav a` altındaki
  stilleri de devralmaz; `.mobile-sheet a` kuralları bu yüzden ayrıca tanımlıdır.
- `/rehber` gerçek bir dizin sayfasıdır (hem statik ön render hem SPA rotası). Breadcrumb'ın
  ikinci kademesi buraya işaret eder; öncesinde `/#rehberler` fragment'ıydı.
- `frontend/nginx.conf` içinde `location = /rehber` **şarttır**: `location ^~ /rehber/` sondaki
  eğik çizgisiz yolu yakalamaz, istek `location /` üzerinden 301 ile `/rehber/`'e giderdi.
  Sitemap ve canonical `/rehber` olduğu için doğrudan 200 dönmesi gerekir.
- iOS Safari notu: eski mobil menü `<details>` + `summary{display:grid}` kullanıyordu; WebKit
  `<summary>` display'i değiştirildiğinde açma davranışını düşürür, menü iPhone'da hiç açılmıyordu.
  Yeni menü `<button>` + React state kullanır. Mobil panelde body kaydırma kilidi de
  `overflow:hidden` yerine `position:fixed` + scroll geri yükleme ile yapılır (iOS'ta overflow yetmez).

## Bilinen sorunlar

0. Prod Nginx `http` bloğunda `ssl_protocols TLSv1 TLSv1.1 TLSv1.2 TLSv1.3;` (dağıtım varsayılanı). Site conf'u `onsaltinanaliz.com` için TLSv1.2/1.3'e daraltıyor, ama başka bir server bloğu eklenirse eski protokoller devreye girer.
1. `/model-service/v1/training/run`, `/v1/training/backfill` ve `/v1/snapshots` gateway üzerinden kimlik doğrulaması olmadan herkese açık. `/v1/snapshots` gövdesindeki `features` doğrudan eğitim tablosuna yazıldığı için bu bir veri bütünlüğü riski.
2. `automatic_learning_service.collect_once` snapshot'ı `display_price=closes[-1]` (Binance) ile yazıyor; `observations` PK `trade_date` olduğu için saatlik job, frontend'in yazdığı gerçek Harem fiyatını ezip `basis_usd`'yi 0'a çekiyor.
3. `.env.development` dosyalarında hâlâ `example.com` yer tutucuları var (development profili kullanılamaz durumda).
4. Kök dizindeki `api-gateway/`, `market-service/`, `model-service/` klasörleri ölü `.venv` kalıntısı.
5. Grafikteki "vadesi dolan tahminler" katmanı `/v1/learning/history` verisi biriktikçe dolar; ilk 7 günlük hedefler kapanana kadar boş görünür.
