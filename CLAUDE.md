# CLAUDE.md — Proje İndeksi

Ons altın (PAXG/USDT referanslı) fiyat tahmin platformu. React SPA + 3 FastAPI mikroservisi + SQLite.
Prod: https://onsaltinanaliz.com (Docker Compose + host Nginx, sunucu 5.75.148.203).

## Repo haritası

```
frontend/                 React 19 + TS + SCSS + Vite (tek dosya UI: src/App.tsx, 481 satır)
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

- `src/App.tsx` tek dosya: dashboard + SEO makale sayfaları + grafik + kredi senaryo hesabı.
- `API_BASE` şablonu: `.env.production` → `{origin}` (aynı origin, nginx proxy), `.env.localhost` → `http://{host}:8000`.
- Canlı veri: Binance WS (`wss://stream.binance.com:9443/ws/paxgusdt@ticker`) + Harem socket.io (`wss://hrmsocketonly.haremaltin.com`, ONS ve USDTRY) — bunlar tarayıcıdan **doğrudan**, gateway'siz.
- Tahmin: `POST /model-service/v1/predict` (700 ms debounce); istek düşerse `src/data/model.json` ile tarayıcı içi ensemble fallback.
- Günde bir kez `POST /model-service/v1/snapshots` (Europe/Istanbul günü, `snapshotDayRef` ile tekilleştirme).
- SEO: `scripts/generate-seo-pages.mjs` build sonrası `App.tsx` içindeki `SEO_ARTICLES` dizisini parse edip `dist/rehber/<id>/index.html` üretir — **dizinin sözdizimi bozulursa build kırılır** (`const avg` bitiş işaretçisine bağlı).

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

- İçerik kaynağı: `frontend/src/data/seo-articles.json` (31 makale). Hem `App.tsx` hem
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

- `SiteNav` (`App.tsx`) `<details>` yerine kontrollü React state kullanır: dışarı tıklama,
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
