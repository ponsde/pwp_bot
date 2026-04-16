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
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
        libgl1 \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir "mcp[cli]" prompt_toolkit httpx

COPY . .

# Overlay our patched vikingbot (with MCP + CORS + api_key fixes) over
# the PyPI version. This bypasses the Rust CLI build issue and includes
# PR #1392 MCP support that hasn't been released yet.
COPY vikingbot_pkg/ /usr/local/lib/python3.11/site-packages/vikingbot/

# Overlay the built SPA
COPY --from=frontend /app/web-studio/dist ./web-studio/dist

# Startup script: generate ov.conf from env vars, start vikingbot + FastAPI
COPY <<'STARTUP' /app/start.sh
#!/bin/bash
set -e

# Generate ov.conf from environment variables
mkdir -p /root/.openviking
cat > /root/.openviking/ov.conf <<CONF
{
  "storage": {"agfs": {"port": 1834}},
  "embedding": {
    "dense": {
      "api_base": "${LLM_API_BASE}",
      "api_key": "${LLM_API_KEY}",
      "provider": "openai",
      "dimension": 1024,
      "model": "${EMBEDDING_MODEL:-BAAI/bge-m3}"
    }
  },
  "vlm": {
    "api_base": "${LLM_API_BASE}",
    "api_key": "${LLM_API_KEY}",
    "provider": "openai",
    "model": "${LLM_MODEL}"
  },
  "bot": {
    "agents": {
      "model": "openai/${LLM_MODEL}",
      "api_key": "${LLM_API_KEY}",
      "api_base": "${LLM_API_BASE}",
      "max_tool_iterations": 10,
      "memory_window": 30,
      "system_prompt": "你是中药上市公司财报智能问数助手。\n\n## 数据库信息\n- SQLite 数据库，4张表：core_performance_indicators_sheet（核心指标）、balance_sheet（资产负债）、income_sheet（利润）、cash_flow_sheet（现金流量）\n- 每张表共有字段：serial_number, stock_code, stock_abbr, report_period, report_year\n- report_period 格式：2023FY（年报）、2024HY（半年报）、2024Q1/Q3（季报）。注意没有 Q2/Q4，用 HY 和 FY 代替\n- 不确定有哪些公司时，用 SELECT DISTINCT stock_code, stock_abbr FROM core_performance_indicators_sheet 查询\n- stock_abbr 是中文简称，查询时用 LIKE 模糊匹配更稳\n\n## 工具使用\n- mcp_fin_query：首选。输入自然语言问题，自动生成SQL查询\n- mcp_fin_sql：直接写 SQL\n- mcp_fin_tables：查看表结构\n- mcp_fin_import_pdf：将上传的PDF财报导入数据库\n\n## 回答要求\n- 基于查询结果给出准确简洁的回答，金额单位万元\n- 引用来源：回答末尾附上 sources 中的数据来源\n- 对比类问题用表格\n\n## 文件上传\n根据文件类型判断：PDF财报用 mcp_fin_import_pdf，其他文档用 openviking_add_resource，图片直接回应"
    },
    "channels": [
      {"type": "openapi", "api_key": "${VIKINGBOT_API_KEY:-taidi-bot-key-2026}"},
      {"type": "bot_api", "id": "default", "enabled": true, "api_key": "${VIKINGBOT_API_KEY:-taidi-bot-key-2026}"}
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
          "env": {"SQLITE_DB_PATH": "${SQLITE_DB_PATH:-data/db/finance.db}"},
          "tool_timeout": 120,
          "enabled_tools": ["*"]
        }
      }
    }
  }
}
CONF

export OPENVIKING_CONFIG_FILE=/root/.openviking/ov.conf
export OPENAI_API_KEY="${LLM_API_KEY}"
export OPENAI_API_BASE="${LLM_API_BASE}"

# Start vikingbot gateway in background
vikingbot gateway --port 18790 &
VIKINGBOT_PID=$!

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
