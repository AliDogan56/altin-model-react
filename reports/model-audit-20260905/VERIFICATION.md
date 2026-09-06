# Doğrulama — 6 Eylül 2026

## Çalıştırılan kontroller

| Kapsam | Sonuç |
|---|---|
| Model-service testleri | **106 geçti** |
| Market-service testleri | **48 geçti** |
| API gateway testleri | **5 geçti** |
| Frontend Vitest | **182 geçti**, 22 test dosyası |
| Production frontend build | Başarılı; makale indeksi + Vite + SEO statik sayfaları |
| `git diff --check HEAD` | Başarılı |
| Araştırma pipeline | 43 aday × 3 vade × 3 dış fold tamamlandı |
| Gerçek trainer eğitimi | Aynı frozen snapshot'ta sıfırdan diagnostic candidate üretildi |
| Candidate → model-service entegrasyonu | [Makine çıktısı](integration_verification.json): deterministik, son training/serving getiri farkı **0.0** |
| Legacy sayısal uyumluluk | Yerel bundled artifact için bağımsız eski formül ile yeni service mean/error farkı **0.0** |
| Provenance gate | Mevcut doğrulanmamış CSV için promotion gerçekten reddedildi |
| Grafik okunabilirliği | Üç SVG Quick Look PNG önizlemeleriyle görsel kontrol edildi |

Python 3.14.6, NumPy 2.5.2, scikit-learn 1.9.0 ortamı kullanıldı. Market/gateway
testleri model-service sanal ortamından çalıştırıldı; production container testi
oldukları iddia edilmiyor. 60-iterasyonla sınırlandırılmış sentetik eğitim testleri
convergence warning üretiyor. Joblib/NumPy, FastAPI/Starlette deprecation uyarıları
var; bunlar test başarısızlığı değil. Gerçek 600-max-iter candidate koşusunda
convergence uyarısı görülmedi. Araştırma uyarıları ayrıca kayıtlı.

## Typecheck sınırı

`tsc --noEmit` hâlâ önceden mevcut şu dört hatayla başarısız:

```text
src/app/csp.test.ts: node:crypto, node:fs, node:path tipleri bulunamıyor
src/app/csp.test.ts: __dirname tipi bulunamıyor
```

İlgili dosya bu model çalışmasında değiştirilmedi. Yeni model/FE değişikliklerinde
başka TypeScript hatası raporlanmadı. Vite build typecheck yerine geçmez; sonuçlar
bu yüzden ayrı bildirildi.

## Yeniden üretme

`backend/model-service` dizininde:

```sh
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/run_model_audit.py --dataset ../../reports/model-audit-20260905/dataset_snapshot.csv --output ../../reports/model-audit-20260905
.venv/bin/python scripts/summarize_model_audit.py ../../reports/model-audit-20260905
.venv/bin/python scripts/verify_model_audit.py ../../reports/model-audit-20260905
.venv/bin/python scripts/render_model_audit_report.py ../../reports/model-audit-20260905
```

Verifier yalnız bu çalışmada yerel olarak üretilmiş güvenilir candidate joblib'ini
okur; rastgele bir kaynaktan indirilen joblib/pickle dosyalarını çalıştırmayın.
Eğitim hash'i ve evaluator hash'i mevcut kodla eşleşti. Verifier eğitim yapmaz,
aktif modeli değiştirmez, veri indirmez; yalnız doğrulama JSON'unu yazar.

## Yapılmayanlar / kalan önkoşullar

- Canlıya deploy, aktif artifact değiştirme veya commit/push yapılmadı.
- Gerçek yayın/vintage metadata'lı beş yıllık makro veri temin edilmedi; PIT builder
  testli bir offline altyapıdır, eski CSV'yi doğru PIT veriye dönüştürmüş değildir.
- Futures-proxy tarihçenin gerçek spot olduğu doğrulanmadı.
- Ledger/monitoring production'da etkinleştirilmedi; gerçek forward sonuçlar yok.
  Otomatik reconciliation scheduler yok; doğrulanmış verilerle testli offline
  fonksiyon operatör tarafından çağrılabilir.
- Raporun HTML görünümü uygulama tarayıcısında localhost zaman aşımına uğradı;
  SVG'lerin kendileri yerel dosya render'ı ile incelendi. Geçici önizleme sunucusu
  kapatıldı. Browser E2E yaptığımız iddia edilmiyor.
- Mevcut yerel servis tarafından yenilenen asıl CSV'nin dört satırlık farkı korundu.
  Deneyler yalnız hash'i sabitlenmiş rapor snapshot'ını kullanır.
