# Quickstart

## 1. Docker (recommended)

```sh
git clone https://github.com/mirecekd/f-r-i-d-a-y.git && cd f-r-i-d-a-y
cp .env.example .env
$EDITOR .env                 # set GEMINI_API_KEY; the rest is optional
docker compose up -d --build
```

Open <http://127.0.0.1:8670>, click the orb and allow the microphone (browsers need HTTPS or localhost for it).
To use the prebuilt image instead of building, set `image: ghcr.io/mirecekd/f-r-i-d-a-y:latest` and run
`docker compose pull && docker compose up -d`.

Data (uploads, models, preferences) lives in `./data`.

## 2. Without Docker

```sh
cd frontend && npm ci && npm run build        # builds into backend/static
cd ../backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
GEMINI_API_KEY=your-key FRIDAY_DATA_DIR=./data .venv/bin/uvicorn app.main:app --port 8670
```

## 3. Optional integrations

| What | Set in `.env` |
|---|---|
| Memory service (orbs, recall) | `AGENTMEMORY_URL`, `AGENTMEMORY_SECRET` |
| MCP hub | `MCP_HUB_URL`, `MCP_HUB_TOKEN` (see `backend/mcp_servers.json`) |
| LiteLLM models | `LITELLM_BASE_URL`, `LITELLM_API_KEY` |
| Hermes agent | `HERMES_URL`, `HERMES_KEY` |

Without them Friday still works: voice, 3D scene, models, views, images and web search need only the Gemini key.

## 4. Put it behind authentication

Friday has no login. Expose it only through a reverse proxy with SSO or basic auth and TLS; the compose file publishes
the port on `127.0.0.1` for that reason.
