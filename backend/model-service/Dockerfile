FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/model-service/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/model-service/app ./app
COPY backend/model-service/data/xauusd_training_5y.csv ./data/xauusd_training_5y.csv
# Build sırasında **eğitim yapılmaz.** Önceden burada bir model eğitilip imaja
# gömülüyordu; sonucu şuydu: imaj her yeniden kurulduğunda model yeniden eğitiliyor
# ve hangi ufukların açık olduğu değişebiliyordu. Yani modeli eğitim takvimi değil
# **deploy takvimi** belirliyordu — 2026-09-03'te bir frontend dağıtımı 7 günlük
# ufku sessizce kapattı (ağırlık 0,92 -> 0,00).
#
# Eğitim artık yalnız `automatic_learning_service`'te. Soğuk açılışta model
# bulunmaz; iş 2 saniye sonra ilk turunu koşar ve model olmadığı için
# `previous_rows = 0` olur, eşik kendiliğinden aşılır ve eğitim tetiklenir
# (ölçüldü: eğitim 1,1 sn). O ~3 saniyelik boşlukta `/v1/predict` 503 döner
# ve arayüz nötr yedeğe düşer — sessizce yanlış sayı göstermez.
RUN mkdir -p /models
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
