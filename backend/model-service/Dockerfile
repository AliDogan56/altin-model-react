FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/model-service/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/model-service/app ./app
COPY frontend/src/data/model.json ./data/initial_model.json
RUN mkdir -p /app/models
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
