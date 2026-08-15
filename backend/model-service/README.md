# FastAPI Backend

API uçları:

- `GET /health`: ortam ve aktif model
- `POST /v1/predict`: Binance referanslı tahmin
- `POST /v1/snapshots`: günlük Binance eğitim kaydı + Harem karşılaştırma fiyatı
- `GET /v1/learning/metrics`: gerçekleşmiş hata metrikleri
- `POST /v1/training/run`: scikit-learn MLP yeniden eğitimi

Yeniden eğitim en az 80 tam örnek ister. 180 günlük hedef nedeniyle ilk tam eğitim setinin oluşması doğal olarak zaman alır.
