# XAU/USD Model Service

Model, son beş yıllık günlük XAU/USD kapanışları ve tarihsel olarak hizalanmış
19 teknik/makro özellik üzerinde birbirinden bağımsız 7, 14 ve 30 günlük MLP
toplulukları eğitir. Her ufuk kendi purge boşluklu walk-forward doğrulamasını ve
etiket kesimini kullanır; baz tahmini yenemeyen modelin ağırlığı diğer ufukları
etkilemeden sıfırlanır. Güncel özellikler veri setinde kalır fakat ilgili hedef
gerçekleşene kadar o ufkun eğitimine alınmaz.

API uçları:

- `GET /health`: ortam ve aktif model
- `POST /v1/predict`: XAU/USD referanslı tahmin
- `GET /v1/learning/metrics`: gerçekleşmiş hata metrikleri
- `POST /v1/training/run`: scikit-learn MLP yeniden eğitimi

Yeniden eğitim en az 300 tam örnek ister. Docker imajı oluşturulurken sürümlenen
XAU/USD CSV'sinden başlangıç modeli deterministik olarak eğitilir. Otomatik
öğrenme varsayılan olarak beş yeni işlem günü oluştuğunda modeli yeniler.
