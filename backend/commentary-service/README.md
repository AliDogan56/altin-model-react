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

## Testler

```bash
backend/commentary-service/.venv/bin/python -m pytest backend/commentary-service/tests
```

Testler `DATA_DIR`'ı geçici dizine alır, mock LLM kullanır, ağa çıkmaz (22 test).
