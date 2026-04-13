# syntax=docker/dockerfile:1.6

# --- Stage 1: build the React SPA ---
FROM node:22-alpine AS frontend
WORKDIR /app/web-studio

COPY web-studio/package.json web-studio/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web-studio/ ./
RUN npm run build


# --- Stage 2: Python runtime ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Overlay the built SPA on top of the source copy (which excluded web-studio
# internals via .dockerignore).
COPY --from=frontend /app/web-studio/dist ./web-studio/dist

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
