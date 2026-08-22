# Altın Ons Öğrenen Model Platformu

Ana IntelliJ projesinde frontend ve backend ana modülleri; backend altında üç mikroservis modülü bulunur:

- `frontend/`: React + TypeScript/TSX + SCSS + Vite
- `backend/api-gateway/`: Dışarıya açık tek API girişi ve servis rota kayıtları
- `backend/market-service/`: XAU/USD, FRED ve haber verileri
- `backend/model-service/`: Sinir ağı, SQLite öğrenme verisi, otomatik toplama ve yeniden eğitim job'u

## Veri disiplini

- Eğitim, yeniden eğitim ve hata ölçümü: **XAU/USD**
- Canlı fiyat: **Harem ONS/XAUUSD**
- Bağımsız tahmin hedefleri: 7, 14 ve 30 gün.
- Lokal ortamda üç mikroservis ortak `backend/data/gold_platform_localhost.sqlite3` SQLite dosyasını kullanır.
- Gateway, market ve model tabloları aynı dosyada servis bazında ayrılmıştır.

## Lokal kurulum

```bash
pnpm --dir frontend install
python3.12 -m venv backend/api-gateway/.venv
backend/api-gateway/.venv/bin/pip install -r backend/api-gateway/requirements.txt
python3.12 -m venv backend/market-service/.venv
backend/market-service/.venv/bin/pip install -r backend/market-service/requirements.txt
python3.12 -m venv backend/model-service/.venv
backend/model-service/.venv/bin/pip install -r backend/model-service/requirements.txt
chmod +x start-profile.sh start-local.sh
./start-profile.sh localhost
```

- Mac: `http://127.0.0.1:5173`
- Yerel ağ: `http://192.168.1.103:5173`
- API Gateway: `http://127.0.0.1:8000`
- Market Service: `http://127.0.0.1:8001/docs`
- Model Service: `http://127.0.0.1:8002/docs`

API Gateway `0.0.0.0:8000` üzerinde yerel ağa açıktır. Market ve Model servisleri yalnızca `127.0.0.1` üzerinde dinler; ağdaki diğer cihazlar `8001` ve `8002` portlarına doğrudan erişemez.

## Ortamlar

| Ortam | Frontend | Backend servisleri |
|---|---|---|
| localhost | `frontend/.env.localhost` | `backend/*/.env.localhost` |
| development | `frontend/.env.development` | `backend/*/.env.development` |
| production | `frontend/.env.production` | `backend/*/.env.production` |

Development ve production adresleri sunucu kurulduğunda gerçek alan adlarıyla değiştirilmelidir. Şu anda `localhost` profili aktiftir.

```bash
./start-profile.sh localhost
./start-profile.sh development
./start-profile.sh production
```

## Öğrenme döngüsü

Frontend yalnızca API Gateway'e bağlanır. Gateway URL'lerinde servis adı zorunludur: `/market-service/v1/market/*` Market Service'e, `/model-service/v1/*` Model Service'e yönlenir. Gateway servis adı önekini kaldırıp kalan yolu hedef servise iletir. Mikroservis hataları Gateway'de standart hata gövdesine çevrilir ve `X-Trace-Id` ile loglanır. Model servisi saatlik job ile verileri toplar, vadesi dolan hedefleri kapatır ve yeterli yeni örnek oluştuğunda MLP modelini yeniden eğitir.
