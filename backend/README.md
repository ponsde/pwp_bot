# backend

FastAPI service for the web-studio frontend.

## Dev

```bash
# 1. Backend (port 8000)
uvicorn backend.server:app --reload --port 8000

# 2. Frontend (port 3000, proxies API calls via VITE_API_BASE_URL)
cd web-studio
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

Open http://localhost:3000 — the `/sessions` route is the ask page.

## Prod

Build the frontend once, then run the backend; it serves the SPA at `/` and
the API at `/api/*`:

```bash
cd web-studio && npm run build && cd ..
uvicorn backend.server:app --host 0.0.0.0 --port 8000
```

## Endpoints

- `POST /api/ask` — `{question, session_id?}` → answer + SQL + rows + chart URL
- `GET  /api/stats` — DB overview
- `GET  /api/health` — liveness
- `/charts/*` — rendered chart jpgs from `result/`
- `/*` — SPA fallback (index.html) when `web-studio/dist/` exists
