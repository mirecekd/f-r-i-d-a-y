<img src="https://capsule-render.vercel.app/api?type=waving&height=120&color=0:202323,55:303635,100:e7ac80&text=F.R.I.D.A.Y.&fontColor=f1d6b4&fontSize=40&fontAlignY=45&desc=Quickstart&descSize=18&descColor=f1d6b4&descAlignY=68" width="100%" alt="" />

# F.R.I.D.A.Y. - quickstart

Everything below gets you from a clone to a talking assistant in a few minutes. Friday is a web app: a backend in a container and a browser tab with the 3D scene.

## 0. What you need (one time)

| What | Why | Check |
|---|---|---|
| Docker with Compose | runs the backend and the built frontend | `docker compose version` |
| A Gemini API key | the voice and web search | key from Google AI Studio |
| A browser with a microphone | you talk to it | `localhost` or HTTPS is required |

## 1. Docker (recommended)

```sh
git clone https://github.com/mirecekd/f-r-i-d-a-y.git && cd f-r-i-d-a-y
cp .env.example .env
$EDITOR .env                 # set GEMINI_API_KEY; the rest is optional
docker compose up -d --build
```

Open <http://127.0.0.1:8670>, click the orb and allow the microphone (browsers need HTTPS or localhost for it).

Check it works: say "hello"; the orb pulses while Friday answers by voice. Pick the voice and the language in the settings panel.
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

Press the round STOP button (or Esc) at any time to halt playback, the microphone and every running tool.

<img src="https://capsule-render.vercel.app/api?type=waving&height=110&section=footer&color=0:e7ac80,55:303635,100:202323" width="100%" alt="" />
