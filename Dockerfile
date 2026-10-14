FROM node:22-alpine AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-hin tesseract-ocr-kan && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend/app ./app
COPY --from=frontend /web/dist ./web
RUN useradd --create-home appuser && mkdir /app/data && chown appuser:appuser /app/data
USER appuser
ENV DATA_DIR=/app/data STATIC_DIR=/app/web
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
