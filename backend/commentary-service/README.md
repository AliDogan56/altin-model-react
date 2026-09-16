# commentary-service

Ons altın (XAU/USD) için son okuyucuya yönelik Türkçe piyasa yorumu üretir: "altın şu an neden düşüyor / yükseliyor".
Yorum istek başına üretilmez; arka plan işi fiyatı izler, eşik aşılınca (ve son üretimden en az bir saat geçmişse)
beş rollük LLM turunu koşturur ve sonucu diske yazar. API her zaman son metni okur (yanıt milisaniye düzeyinde).

## Mimari

```
job (asyncio, 5 dk)  →  fiyat kontrolü (PAXG / GC=F)  →  should_regenerate?
                                                          ├─ hayır: bekle
                                                          └─ evet: snapshot_service (LBMA, Yahoo, FRED, CFTC, RSS)
                                                                   → commentary_pipeline (5 LLM rolü, zincirli yedek)
                                                                   → output_audit (sayı ve jargon denetimi)
                                                                   → commentary_store (versions/<sürüm>/commentary.json, `current`)
GET /v1/commentary/latest  →  commentary_store.latest()   (üretim tetiklemez)
```

| Katman | Dosya |
|---|---|
| Ayar (ortam) | `app/config.py` — `APP_ENV`, `DATA_DIR`, `LLM_CONFIG_PATH`, tetik eşikleri |
| LLM ayarı (dosya) | `llm.toml` — sağlayıcılar (`kind`: anthropic / openai_compatible / mock), roller, yedek zincirleri |
| Veri | `app/services/{price_data,macro_data,live_price,market_inputs,news}_service.py` |
| Teknik hesap | `app/services/technical/`, `base_cone.py` |
| LLM | `llm_config.py` (doğrulama), `llm_gateway.py` (sağlayıcılar, `ask`), `commentary_pipeline.py`, `output_audit.py` |
| İş ve depo | `commentary_job_service.py`, `regeneration_policy.py`, `commentary_store.py` |
| Uçlar | `app/controllers/commentary_controller.py`, `health_controller.py` |

Rol istemleri `app/prompts/<rol>.md`; istem paketleri ve şema anahtarları bilerek Türkçedir (model Türkçe yazar, denetim
aynı anahtarları okur). Dış API sözleşmesi (`app/models/api_models.py`) İngilizcedir.

## Uçlar

| Uç | Açıklama |
|---|---|
| `GET /health`, `GET /ready` | Sağlık; `/ready` yayımlanmış yorum yoksa 503 |
| `GET /v1/commentary/latest` | Son yorum (JSON: başlık, manşet, özet, yedi bölüm, canlı fiyat, sürüm, yaş) |
| `GET /v1/commentary/latest/text` | Aynı içerik düz metin |
| `GET /v1/commentary/job` | İş durumu: son kontrol, son karar, son üretim, hata, LLM zincirleri |
| `POST /v1/commentary/regenerate` | Yönetici (bearer `COMMENTARY_ADMIN_TOKEN`); bir sonraki döngüde zorla üretim |

Gateway üzerinden: `/commentary-service/v1/commentary/latest`.

## Kurulum

```bash
python3.12 -m venv backend/commentary-service/.venv
backend/commentary-service/.venv/bin/pip install -r backend/commentary-service/requirements.txt
cp backend/commentary-service/.env.secrets.example backend/commentary-service/.env.secrets   # anahtarları doldur
backend/commentary-service/.venv/bin/python backend/commentary-service/scripts/check_llm.py   # ayar ve anahtar doğrulaması
backend/commentary-service/.venv/bin/python backend/commentary-service/run.py localhost
```

`.env.secrets` git dışıdır; `run.py` profil dosyasından sonra yükler, Docker'da `env_file` ile verilir. Servis açılışta
`llm.toml`'daki zincirlerde geçen her sağlayıcının anahtarını doğrular; eksikse **ayağa kalkmaz** (RuntimeError).

Anthropic sağlayıcısı isteğe bağlıdır: yalnız `llm.toml`'da kullanılıyorsa `pip install anthropic` gerekir.

## Üretim politikası

| Değişken | Varsayılan | Anlamı |
|---|---|---|
| `CHECK_INTERVAL_SECONDS` | 300 | Fiyat kontrol sıklığı |
| `TRIGGER_MOVE_PCT` | 0.5 | Son üretimden bu yana fiyat oynaması eşiği (yüzde) |
| `MIN_INTERVAL_MINUTES` | 60 | İki üretim arası asgari süre (eşik aşılsa da) |
| `MAX_AGE_MINUTES` | 240 | Fiyat oynamasa da tazeleme; 0 = kapalı |
| `PIPELINE_MODE` | full | `full`: beş rol; `fast`: yalnız metin yazarı (son brifle) |
| `KEEP_VERSIONS` | 20 | Diskte tutulan sürüm sayısı |

İlk üretim her zaman yapılır. Ölçüm: tam tur Gemini + Groq ücretsiz katmanda ≈ 23 bin token, ≈ 3,5 dk, 0 dolar.

Yeniden başlatmada iş, son üretim zamanı ve fiyatını yayındaki sürümden okur (`_seed_from_store`); deploy tam tur
tetiklemez, karar yine %0,5 hareket / 60 dk / 240 dk kurallarıyla verilir.

## Yorumcu gözcüsü (2026-09-16)

Türkiye'deki tanınmış altın yorumcularının son 72 saatte (`COMMENTATOR_WINDOW_HOURS`) **habere yansıyan** sözlerini
masaya "piyasadaki sesler" olarak verir; metin **ad vermez**, yorumcuları toplu anar (kullanıcı kararı: tek ismi öne
çıkarmamak). Liste üç isim: İslam Memiş, Mehmet Ali Yıldırımtürk, Atilla Yeşilada. Liste `yorumcular.toml` (`[[yorumcu]] ad, sorgu`); kaynak Google News RSS (isim + altın).
Video ya da altyazı çekilmez: YouTube bulut IP'lerini engelliyor, Gemini'ye video vermek tur başına 90–200 bin
token; haber yolu sıfır ek altyapı.

- Ayrı döngü: iş her `COMMENTATOR_REFRESH_MINUTES` (360; 0 = kapalı) dakikada bir RSS'i çeker, başlıkları kelime
  kümesi benzerliğiyle tekilleştirir (aynı söz on sitede çıkıyor), `commentator_scout` rolüyle **tek** LLM çağrısı
  yapar ve `latest/yorumcular.json` yazar. Ölçüldü: 8 başlık, 1,9k giriş / 450 çıkış token, 2,3 sn (Groq).
- Masaya giden kayıt adsızdır: etiket (`Yorumcu 1..n`, liste sırası), yön (`yukselis/dusus/temkinli/karisik/belirsiz`),
  vade, ana iddia, dayanak (kaynak + saat), haber sayısı; yanında sayım (izlenen, konuşan, yön dağılımı, baskın yön). **Sayısal hedefler masaya gitmez**: özet cümlesinden çıkarılır (`strip_numbers`, "… dolara"),
  yalnız kayıttaki `sayisal_hedefler` alanında durur. Masanın kuralı "sayılar yalnız veri paketinden gelir".
- Baş analist brife `piyasa_sesleri` (en fazla iki cümle, "haberlere yansıyan tanınmış yorumcular", ayrışma varsa
  o da) yazar; anlatıcı bunu **sekizinci bölüm** olarak yazar: `sesler` / "Piyasa ne diyor", büyük resim ile takvim
  arasında, 30–45 kelime, ad vermeden. Brif boşsa bölüm yazılmaz (yedi bölüm); eksik ya da fazla bölüm düzeltme turu ister. Anlatıcıya giden brifteki sayılar da temizlenir, denetim havuzuna girmez.
- Ad denetimi: metinde izleme listesindeki bir ad geçerse düzeltme turu; yorumcular toplu anılır.
  24 saatten eski özet masaya gitmez. Yorumcu görüşü değişince tur planlayıcı tam tur ister.
- `/v1/commentary/job` → `commentators` bloğu (son tazeleme, hata, özet). Testler `tests/test_commentators.py`.

## Testler

```bash
backend/commentary-service/.venv/bin/python -m pytest backend/commentary-service/tests
```

Testler `DATA_DIR`'ı geçici dizine alır, mock LLM kullanır, ağa çıkmaz (22 test).
