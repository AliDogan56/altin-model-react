# FastAPI Backend

API uçları:

- `GET /health`: ortam ve aktif model
- `GET /v1/market/xau`: beş yıllık günlük XAU/USD geçmişi
- `GET /v1/learning/metrics`: gerçekleşmiş hata metrikleri
- `POST /v1/training/run`: scikit-learn MLP yeniden eğitimi

Yeniden eğitim en az 80 tam örnek ister. 180 günlük hedef nedeniyle ilk tam eğitim setinin oluşması doğal olarak zaman alır.
