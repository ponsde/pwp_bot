# syntax=docker/dockerfile:1.6

# --- Stage 1: build the React SPA ---
FROM node:22-alpine AS frontend
WORKDIR /app/web-studio

COPY web-studio/package.json web-studio/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web-studio/ ./
ENV VITE_OV_BASE_URL=/ \
    VITE_API_BASE_URL=
RUN npm run build


# --- Stage 2: Python runtime ---
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
        libgl1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir "mcp[cli]" prompt_toolkit httpx

COPY . .

# Overlay the built SPA
COPY --from=frontend /app/web-studio/dist ./web-studio/dist

# Apply the streaming + api_key patches from OpenViking PR #13 / #23 onto
# the pip-installed vikingbot. The script picks up SITE from env.
RUN SITE=/usr/local/lib/python3.12/site-packages \
        bash /app/scripts/bot_streaming_patches/apply.sh

# Startup script: render ov.conf from ov.conf.tmpl (single source of truth,
# shared with local dev), then launch vikingbot + FastAPI.
COPY <<'STARTUP' /app/start.sh
#!/bin/bash
set -e

# Internal api key — not user-configurable because everything is same-origin.
# FastAPI reverse-proxies /bot/v1/* and injects this header on behalf of the browser.
INTERNAL_BOT_KEY="embedded-same-origin-$(head -c 16 /dev/urandom | base64)"
export INTERNAL_BOT_KEY
export BOT_CHANNEL_API_KEY="${INTERNAL_BOT_KEY}"

# Default SQLite path for container
export SQLITE_DB_PATH="${SQLITE_DB_PATH:-/app/data/db/finance.db}"

# Render ov.conf via the same template + generator used locally.
mkdir -p /root/.openviking
REPO_ROOT=/app PYTHON_BIN=python3 \
  python3 /app/scripts/gen_ov_conf.py -o /root/.openviking/ov.conf

export OPENVIKING_CONFIG_FILE=/root/.openviking/ov.conf
# Litellm also reads these for the bot LLM at runtime
export OPENAI_API_KEY="${LLM_API_KEY}"
export OPENAI_API_BASE="${LLM_API_BASE}"

# Start OpenViking HTTP server first — vikingbot's openviking_search /
# memory tools hit http://127.0.0.1:18792; without it the agent loop
# stalls trying unreachable tools and returns empty responses.
openviking-server --host 127.0.0.1 --port 18792 --config /root/.openviking/ov.conf &

# Wait for OV to accept connections before launching the bot
for i in $(seq 1 60); do
  if curl -s http://127.0.0.1:18792/ > /dev/null 2>&1; then
    echo "openviking-server ready"
    break
  fi
  sleep 1
done

# Start vikingbot gateway in background
vikingbot gateway --port 18790 &

# Wait for vikingbot to be ready
for i in $(seq 1 30); do
  if curl -s http://localhost:18790/bot/v1/health > /dev/null 2>&1; then
    echo "vikingbot ready"
    break
  fi
  sleep 1
done

# Start FastAPI (main process)
exec uvicorn backend.server:app --host 0.0.0.0 --port ${PORT:-8000}
STARTUP
RUN chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]
