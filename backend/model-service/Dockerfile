FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/model-service/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/model-service/app ./app
COPY backend/model-service/data/xauusd_training_5y.csv ./data/xauusd_training_5y.csv
# Build sırasında volume yok: yedek artefakt imaja gömülür. Çalışma anında
# yeniden eğitim MODEL_DIR volume'una yazar ve oradan okunur.
RUN python -c "from app.services.trainer import train_model, BUNDLED_ARTIFACT_PATH; train_model(artifact_path=BUNDLED_ARTIFACT_PATH)"
RUN mkdir -p /models
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
