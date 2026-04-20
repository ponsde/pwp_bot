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

# Startup script: generate ov.conf from env vars, start vikingbot + FastAPI
COPY <<'STARTUP' /app/start.sh
#!/bin/bash
set -e

# Internal api key — not user-configurable because everything is same-origin.
# FastAPI reverse-proxies /bot/v1/* and injects this header on behalf of the browser.
INTERNAL_BOT_KEY="embedded-same-origin-$(head -c 16 /dev/urandom | base64)"

# Generate ov.conf from environment variables
mkdir -p /root/.openviking
cat > /root/.openviking/ov.conf <<CONF
{
  "embedding": {
    "dense": {
      "api_base": "${OV_EMBEDDING_API_BASE}",
      "api_key": "${OV_EMBEDDING_API_KEY}",
      "provider": "openai",
      "dimension": ${OV_EMBEDDING_DIMENSION:-1024},
      "model": "${OV_EMBEDDING_MODEL}"
    }
  },
  "vlm": {
    "api_base": "${OV_VLM_API_BASE}",
    "api_key": "${OV_VLM_API_KEY}",
    "provider": "openai",
    "model": "${OV_VLM_MODEL}"
  },
  "bot": {
    "agents": {
      "model": "openai/${OV_VLM_MODEL}",
      "api_key": "${OV_VLM_API_KEY}",
      "api_base": "${OV_VLM_API_BASE}",
      "max_tool_iterations": 10,
      "memory_window": 30,
      "system_prompt": "你是中药上市公司财报智能问数助手。\n\n## 数据库信息\n- SQLite 数据库，4张表：core_performance_indicators_sheet（核心指标）、balance_sheet（资产负债）、income_sheet（利润）、cash_flow_sheet（现金流量）\n- 每张表共有字段：serial_number, stock_code, stock_abbr, report_period, report_year\n- report_period 格式：2023FY（年报）、2024HY（半年报）、2024Q1/Q3（季报）。注意没有 Q2/Q4，用 HY 和 FY 代替\n- 不确定有哪些公司时用 SELECT DISTINCT stock_code, stock_abbr FROM core_performance_indicators_sheet 查询\n- stock_abbr 是中文简称，查询时用 LIKE 模糊匹配\n\n## 工具使用\n- mcp_fin_query：首选，自然语言查询\n- mcp_fin_sql：直接写 SQL\n- mcp_fin_tables：查看表结构\n- mcp_fin_import_pdf：导入上传的PDF财报\n\n## 回答要求\n- 金额单位万元\n- 引用来源：回答末尾附上 sources 中的数据来源\n- 对比类问题用表格\n\n## 文件上传\n根据文件类型判断：PDF财报用 mcp_fin_import_pdf，其他文档用 openviking_add_resource，图片直接回应"
    },
    "channels": [
      {"type": "openapi", "api_key": "${INTERNAL_BOT_KEY}"},
      {"type": "bot_api", "id": "default", "enabled": true, "api_key": "${INTERNAL_BOT_KEY}"}
    ],
    "gateway": {"host": "0.0.0.0", "port": 18790},
    "sandbox": {"backend": "direct", "mode": "shared"},
    "ov_server": {"mode": "local"},
    "tools": {
      "mcp_servers": {
        "fin": {
          "type": "stdio",
          "command": "python3",
          "args": ["/app/backend/taidi_mcp_server.py"],
          "env": {
            "SQLITE_DB_PATH": "${SQLITE_DB_PATH:-/app/data/db/finance.db}",
            "LLM_API_BASE": "${LLM_API_BASE}",
            "LLM_API_KEY": "${LLM_API_KEY}",
            "LLM_MODEL": "${LLM_MODEL}",
            "LLM_TIMEOUT": "${LLM_TIMEOUT:-60}"
          },
          "tool_timeout": 120,
          "enabled_tools": ["*"]
        }
      }
    }
  }
}
CONF

# Tell FastAPI proxy to inject the internal key
export INTERNAL_BOT_KEY
export OPENVIKING_CONFIG_FILE=/root/.openviking/ov.conf
# Litellm reads these for the bot LLM
export OPENAI_API_KEY="${OV_VLM_API_KEY}"
export OPENAI_API_BASE="${OV_VLM_API_BASE}"

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
