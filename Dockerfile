FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend ./backend
COPY frontend ./frontend

# Fly mounts the persistent volume here; ensure dirs exist so the app can
# create files in them on first boot.
RUN mkdir -p /data/uploads

ENV DB_PATH=/data/horse.db \
    UPLOADS_DIR=/data/uploads \
    PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --app-dir backend"]
