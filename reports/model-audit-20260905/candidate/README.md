# Trainer doğrulama çıktısı — diagnostic candidate, production değil

Esas çıktı: `xauusd_candidate_checked.joblib` ve aynı adlı JSON metadata.
`xauusd_candidate.joblib` ilk kontrol koşusudur; esas çıktı ek hedef-tutarlılık
kontrolleri ve eğitim-kodu hash'i tamamlandıktan sonra oluşturulmuştur.
İki koşu aynı sayısal tahmin/metrikleri üretmiştir. Hiçbiri aktive edilmemiştir.

- Veri snapshot SHA-256: `c7a87939ea08cac69112b12576015dabd730d57f475fa1d4b1aca67c7cd3e240`
- Model: `xauusd-mlp-candidate-20260906T032755333823Z`
- Eğitim-kodu SHA-256: `8804cdcb4695b77aa3b011fd6bfcdf4f0695a3d38b98be4af3ad4becc9e92bbd`
- Süre: 0.424 saniye (yerel Python 3.14.6 / sklearn 1.9.0; ağ max_iter=600).
- Mevcut bundled champion dosyasının eğitim öncesi/sonrası SHA-256 değeri aynı.
- Kaynakların point-in-time niteliği doğrulanmamıştır; bu sonuçlar canlıya geçiş kanıtı değildir.

## Önce / sonra: değerlendirme doğruluğu düzeltmesi

Önce sütunları `../legacy_reproduction.json` içindeki `reported` değerleridir:
aynı OOF hedeflerinde ağırlık seçip performans raporlayan eski prosedür. Bu nedenle
bağımsız test değildir. Sonra sütunları bağımsız dış test bloklarının sonuçlarıdır.
Bu tablo bir modelin canlı doğruluğunun arttığını/azaldığını tek başına kanıtlamaz;
eğitim/kalibrasyon pencereleri ve abstention tanımı değişmiştir.

| Ufuk | Eski MAE (getiri) | Yeni MAE (getiri) | Eski MAE skill | Yeni MAE skill | Eski MSE skill | Yeni MSE skill |
|---|---:|---:|---:|---:|---:|---:|
| 7 | 0.02381764 | 0.02400590 | %2.11 | %1.34 | %2.81 | %1.94 |
| 14 | 0.03174852 | 0.03205519 | %0.93 | −%0.027 | %1.65 | %1.34 |
| 30 | 0.04787225 | 0.04943320 | %6.21 | %3.15 | %10.58 | %9.06 |

| Ufuk | Eski yön (tüm satırlar) | Yeni yön (aktif satırlar) | Yeni aktif oran | Nominal %80 bandın dış-test kapsamı |
|---|---:|---:|---:|---:|
| 7 | %62.38 | %63.13 | %33.33 | %71.88 |
| 14 | %62.43 | %55.74 | %66.73 | %74.02 |
| 30 | %70.89 | %63.46 | %66.73 | %70.51 |

Yön doğruluğu doğrudan karşılaştırılabilir değildir: yeni prosedür yalnız ağırlığı
en az 0.2 olan, gerçekleşen ve tahmin edilen getirisi sıfır olmayan satırları sayar;
görüş bildirmemeyi başarılı yön tahmini olarak saymaz. MAE bütün dış-test satırları
üzerindeki ağırlıklı sayısal tahmini ölçer; yalnız aktif işlemlerin MAE'si değildir.

## Ayrımın nasıl korunduğu

Her dış fold: base-fit → target-maturity purge → ağırlık kalibrasyonu →
target-maturity purge → aralık kalibrasyonu → target-maturity purge → dış test.
Scaler yalnız base-fit örneklerinde öğrenilir; eğitim ve yeni model serving aynı
±6 standart sapma clipping fonksiyonunu kullanır. Final future-fit ağırlık/aralık
kalibrasyonu mevcut geçmişi kullanabilir, ancak dış-test metriklerini değiştirmez.

Final model ağırlıkları 7/14/30 için 0.0000 / 0.0998 / 0.3285'tir. İlk iki ufuk
görüş bildirmeme eşiğinin altındadır. %80 nominal kapsamın yaklaşık %71–74 çıkması
aralık kalibrasyonunun henüz yeterli olmadığını gösterir. Candidate metadata'daki
`empirical_coverage: null` final servis bandı için ölçülmüş canlı kapsama olmadığı
anlamına gelir; dış-test sonuçları ayrı `outer_test_coverage` alanında tutulur.

## Doğrulamalar

21 odaklı test geçti: gerçek target-date purge, dış-test hedeflerinin ağırlık veya
aralığı değiştirememesi, train-only scaler, eksik/yanlış/matürleşmemiş hedeflerin
reddi, aday artefakt persistence, champion koruması, sabit boyutlu rolling veri
setinde yeni matürleşen etiketler ve aynı snapshot'ı tekrar eğitmeme.
Mevcut 60-iterasyonlu sentetik test fixture'larının convergence uyarıları beklenir;
gerçek candidate eğitiminde convergence uyarısı görülmedi.
